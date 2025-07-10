import logging
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import requests
import os
import jwt
from datetime import datetime, timedelta
from functools import wraps
import imaplib
import email
import re
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format=
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "your-secret-key-here")

# Use PostgreSQL on Render
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///logistics_production.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Email configuration
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["IMAP_SERVER"] = os.environ.get("IMAP_SERVER", "imap.gmail.com")

# Setup extensions
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": [
    "Authorization", "Content-Type"]}}, supports_credentials=True)
db = SQLAlchemy(app)
mail = Mail(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# API Keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SHIPENGINE_API_KEY = os.environ.get("SHIPENGINE_API_KEY")
openai.api_key = OPENAI_API_KEY

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    company_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    shipments = db.relationship("Shipment", backref="user", lazy=True)
    conversations = db.relationship("Conversation", backref="user", lazy=True)

class Shipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(db.String(100), nullable=False)
    carrier = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    origin = db.Column(db.String(200), nullable=True)
    destination = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    estimated_delivery = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    def serialize(self):
        return {
            "id": self.id,
            "tracking_number": self.tracking_number,
            "carrier": self.carrier,
            "description": self.description,
            "origin": self.origin,
            "destination": self.destination,
            "status": self.status,
            "estimated_delivery": self.estimated_delivery.isoformat() if self.estimated_delivery else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_message = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    # Optional: Track shipment context when message was sent
    shipment_context = db.Column(db.JSON, nullable=True)  # Store shipment data at time of conversation
    
    def serialize(self):
        return {
            "id": self.id,
            "user_message": self.user_message,
            "ai_response": self.ai_response,
            "timestamp": self.timestamp.isoformat(),
            "shipment_context": self.shipment_context
        }

# JWT Token decorator (skips OPTIONS requests)
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "OPTIONS":
            return f(*args, **kwargs)

        token = request.headers.get("Authorization")
        if not token:
            logger.warning("Token is missing for a protected endpoint.")
            return jsonify({"message": "Token is missing"}), 401
        try:
            token = token.replace("Bearer ", "")
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            current_user = User.query.get(data["user_id"])
            logger.info(f"User {current_user.username} authenticated successfully.")
        except Exception as e:
            logger.error(f"Token decoding failed: {e}")
            return jsonify({"message": str(e)}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# ShipEngine API Integration
class ShipEngineAPI:
    def __init__(self):
        self.api_key = SHIPENGINE_API_KEY
        self.base_url = "https://api.shipengine.com/v1"
        self.headers = {
            "API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Validate API key on initialization
        if not self.api_key:
            logger.error("SHIPENGINE_API_KEY not set - tracking will fail")
    
    def _parse_shipengine_response(self, api_response):
        """Parse ShipEngine API response and extract tracking information"""
        try:
            if not api_response:
                logger.warning("No data in ShipEngine response")
                return None
            
            # ShipEngine response format is different from Ship24
            # Extract carrier and status
            carrier = api_response.get('carrier_code', 'Unknown')
            status_code = api_response.get('status_code', '')
            status_description = api_response.get('status_description', 'Unknown')
            
            # Map ShipEngine status to a more readable format
            status = status_description if status_description != 'Unknown' else status_code
            
            # Extract origin/destination from events if available
            events = api_response.get('events', [])
            origin = None
            destination = None
            
            if events:
                # Try to get origin from first event
                first_event = events[0] if events else {}
                origin_addr = first_event.get('city_locality', '')
                origin_state = first_event.get('state_province', '')
                origin_country = first_event.get('country_code', '')
                if origin_addr:
                    origin = f"{origin_addr}, {origin_state}, {origin_country}".strip(', ')
                
                # Try to get destination from ship_to address
                ship_to = api_response.get('ship_to', {})
                if ship_to:
                    dest_city = ship_to.get('city_locality', '')
                    dest_state = ship_to.get('state_province', '')
                    dest_country = ship_to.get('country_code', '')
                    if dest_city:
                        destination = f"{dest_city}, {dest_state}, {dest_country}".strip(', ')
            
            # Extract estimated delivery
            estimated_delivery = api_response.get('estimated_delivery_date')
            
            return {
                "carrier": carrier,
                "status": status,
                "origin": origin,
                "destination": destination,
                "estimated_delivery": estimated_delivery
            }
        except Exception as e:
            logger.error(f"Error parsing ShipEngine response: {e}")
            return None

    def track_shipment(self, tracking_number, carrier_code=None):
        """
        Track shipment using ShipEngine API.
        Enhanced with better error handling and timeout.
        """
        logger.info(f"Tracking shipment: {tracking_number} via ShipEngine API.")
        
        # If no carrier_code provided, try to auto-detect or use common carriers
        if not carrier_code:
            # Try to detect carrier from tracking number format
            carrier_code = self._detect_carrier(tracking_number)
        
        url = f"{self.base_url}/tracking"
        params = {
            'tracking_number': tracking_number
        }
        
        # Add carrier_code if available
        if carrier_code:
            params['carrier_code'] = carrier_code
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=30)
            response.raise_for_status()
            logger.info(f"ShipEngine track_shipment response: {response.status_code}")
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"ShipEngine API: Tracking number {tracking_number} not found")
            elif e.response.status_code == 401:
                logger.error("ShipEngine API: Invalid API key or authentication failed")
            elif e.response.status_code == 422:
                logger.error(f"ShipEngine API: Invalid tracking number format: {tracking_number}")
            else:
                logger.error(f"ShipEngine API HTTP error {e.response.status_code}: {e}")
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"ShipEngine API timeout for tracking number: {tracking_number}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"ShipEngine API network error: {e}")
            return None
    
    def _detect_carrier(self, tracking_number):
        """Attempt to detect carrier from tracking number format"""
        tracking_number = tracking_number.upper().strip()
        
        # FedEx patterns
        if (len(tracking_number) == 12 and tracking_number.isdigit()) or \
           (len(tracking_number) in [14, 20] and tracking_number.isdigit()):
            return 'fedex'
        
        # UPS patterns
        if tracking_number.startswith('1Z') and len(tracking_number) == 18:
            return 'ups'
        
        # USPS patterns
        if (len(tracking_number) in [20, 22] and tracking_number.isdigit()) or \
           tracking_number.startswith(('9400', '9205', '9405')):
            return 'stamps_com'  # ShipEngine's USPS carrier code
        
        # DHL patterns
        if len(tracking_number) == 10 and tracking_number.isdigit():
            return 'dhl_express'
        
        # Default to None if no pattern matches
        logger.info(f"Could not detect carrier for tracking number: {tracking_number}")
        return None

    def get_tracking_info(self, tracking_number):
        """
        Get tracking information using ShipEngine API.
        This method uses the track_shipment method and parses the response.
        """
        logger.info(f"Fetching tracking info for: {tracking_number}")
        
        try:
            # Use the track_shipment method which calls the ShipEngine API
            api_response = self.track_shipment(tracking_number)
            
            # Handle None response (error cases)
            if api_response is None:
                logger.error(f"Failed to get tracking info for {tracking_number}")
                return None
            
            # Parse the successful response
            parsed_data = self._parse_shipengine_response(api_response)
            if parsed_data:
                logger.info(f"Successfully retrieved tracking info for {tracking_number}")
            else:
                logger.warning(f"No tracking data found for {tracking_number}")
                
            return parsed_data
            
        except Exception as e:
            logger.error(f"Unexpected error getting tracking info for {tracking_number}: {e}")
            return None

    def validate_api_key(self):
        """Test if the API key is valid by making a simple request"""
        if not self.api_key:
            return False
            
        url = f"{self.base_url}/carriers"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                logger.info("ShipEngine API key validation successful")
                return True
            elif response.status_code == 401:
                logger.error("ShipEngine API key validation failed: Invalid key")
                return False
            else:
                logger.warning(f"ShipEngine API key validation returned {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error validating ShipEngine API key: {e}")
            return False

# WebSocket Authentication
def authenticate_socket(auth_token):
    """Authenticate WebSocket connection using JWT token"""
    try:
        if not auth_token:
            return None
        
        # Remove 'Bearer ' prefix if present
        if auth_token.startswith('Bearer '):
            auth_token = auth_token[7:]
            
        data = jwt.decode(auth_token, app.config["SECRET_KEY"], algorithms=["HS256"])
        user = User.query.get(data["user_id"])
        return user
    except Exception as e:
        logger.error(f"WebSocket authentication failed: {e}")
        return None

# WebSocket Events
@socketio.on('connect')
def handle_connect(auth):
    """Handle client connection"""
    logger.info("Client attempting to connect to WebSocket")
    
    # Get token from auth data
    token = auth.get('token') if auth else None
    user = authenticate_socket(token)
    
    if not user:
        logger.warning("WebSocket connection rejected - invalid auth")
        return False  # Reject connection
    
    # Join user to their personal room for targeted updates
    join_room(f"user_{user.id}")
    logger.info(f"User {user.username} connected to WebSocket")
    
    # Send connection confirmation
    emit('connection_status', {
        'status': 'connected',
        'message': 'Connected to real-time updates',
        'timestamp': datetime.utcnow().isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected from WebSocket")

@socketio.on('join_shipment_updates')
def handle_join_shipment_updates(data):
    """Join room for shipment updates"""
    token = data.get('token')
    user = authenticate_socket(token)
    
    if user:
        join_room(f"shipments_{user.id}")
        emit('joined_updates', {'status': 'success'})
        logger.info(f"User {user.username} joined shipment updates room")
    else:
        emit('joined_updates', {'status': 'error', 'message': 'Authentication failed'})

def emit_shipment_update(user_id, shipment_data, update_type='status_change'):
    """Emit real-time shipment update to specific user"""
    try:
        # Use socketio.start_background_task to ensure proper context
        def _emit():
            try:
                socketio.emit('shipment_update', {
                    'type': update_type,
                    'shipment': shipment_data,
                    'timestamp': datetime.utcnow().isoformat()
                }, room=f"user_{user_id}")
                logger.info(f"Emitted shipment update to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to emit shipment update in background task: {e}")
        
        # Try to emit directly first, fall back to background task if needed
        try:
            socketio.emit('shipment_update', {
                'type': update_type,
                'shipment': shipment_data,
                'timestamp': datetime.utcnow().isoformat()
            }, room=f"user_{user_id}")
            logger.info(f"Emitted shipment update to user {user_id}")
        except RuntimeError:
            # If we're outside the request context, use background task
            socketio.start_background_task(_emit)
    except Exception as e:
        logger.error(f"Failed to emit shipment update: {e}")

shipengine = ShipEngineAPI()

# OpenAI Integration
class LogisticsAI:
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

    def generate_response(self, user_message, user_shipments=None, context=None, conversation_history=None):
        system_prompt = """You are LogisticsAI, a specialized AI assistant for logistics and shipment tracking services. Your primary role is to help users with:

1. **Shipment Tracking**: Help users understand their shipment statuses, delivery estimates, and tracking information
2. **Logistics Support**: Answer questions about shipping, delivery, carriers, and logistics processes
3. **Problem Resolution**: Assist with delivery issues, delays, and shipment concerns
4. **Information Guidance**: Provide helpful information about shipping methods, transit times, and logistics best practices

Key Guidelines:
- Focus specifically on logistics, shipping, and delivery-related topics
- Be helpful, professional, and solution-oriented
- If asked about non-logistics topics, politely redirect the conversation back to shipping and logistics services
- Use the user's shipment data to provide personalized assistance
- Remember previous conversations to provide contextual responses
- Reference specific shipment details when relevant
- Provide actionable advice and clear explanations
- Be empathetic when dealing with delivery issues or concerns

Always prioritize helping users with their shipping and logistics needs."""
        
        # Add current shipment information
        if user_shipments:
            system_prompt += f"\n\nUser's current shipments: {user_shipments}"
        
        # Add additional context
        if context:
            system_prompt += f"\nAdditional context: {context}"
        
        # Build conversation messages including history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if available
        if conversation_history:
            for conv in conversation_history[-5:]:  # Last 5 conversations for context
                messages.append({"role": "user", "content": conv['user_message']})
                messages.append({"role": "assistant", "content": conv['ai_response']})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=500,
                temperature=0.7
            )
            logger.info("AI response generated successfully.")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return f"I apologize, but I'm having trouble processing your request right now. Error: {str(e)}"

ai_assistant = LogisticsAI()

# Routes
@app.route("/api/register", methods=["POST"])
@cross_origin()
def register():
    logger.info("Register endpoint called.")
    try:
        data = request.get_json()
        if not data:
            logger.warning("Register: No JSON payload received.")
            return jsonify({"message": "No JSON payload received"}), 400

        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        company_name = data.get("company_name")

        if not all([username, email, password]):
            logger.warning("Register: Missing username, email, or password.")
            return jsonify({"message": "Username, email, and password are required"}), 400

        if User.query.filter_by(username=username).first():
            logger.warning(f"Register: Username {username} already exists.")
            return jsonify({"message": "Username already exists"}), 400
        if User.query.filter_by(email=email).first():
            logger.warning(f"Register: Email {email} already exists.")
            return jsonify({"message": "Email already exists"}), 400

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            company_name=company_name
        )
        db.session.add(user)
        db.session.commit()
        logger.info(f"User {username} registered successfully.")

        return jsonify({"message": "User created successfully"}), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during user registration: {e}")
        return jsonify({"message": "Internal server error", "details": str(e)}), 500

@app.route("/api/login", methods=["POST"])
@cross_origin()
def login():
    logger.info("Login endpoint called.")
    try:
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            token = jwt.encode({
                "user_id": user.id,
                "exp": datetime.utcnow() + timedelta(days=7)
            }, app.config["SECRET_KEY"])
            logger.info(f"User {username} logged in successfully.")
            return jsonify({
                "token": token,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "company_name": user.company_name
                }
            }), 200
        logger.warning(f"Login: Invalid credentials for username {username}.")
        return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        logger.error(f"Error during user login: {e}")
        return jsonify({"message": str(e)}), 500

@app.route("/api/shipments", methods=["GET", "POST"])
@token_required
@cross_origin()
def handle_shipments(current_user):
    if request.method == "GET":
        logger.info(f"GET /api/shipments called by user {current_user.username}.")
        try:
            shipments = Shipment.query.filter_by(user_id=current_user.id).all()
            logger.info(f"Retrieved {len(shipments)} shipments for user {current_user.username}.")
            return jsonify({"shipments": [s.serialize() for s in shipments]}), 200
        except Exception as e:
            logger.error(f"Error retrieving shipments: {e}")
            return jsonify({"message": str(e)}), 500
            
    elif request.method == "POST":
        logger.info(f"POST /api/shipments called by user {current_user.username}.")
        start_time = time.time()
        try:
            data = request.get_json()
            tracking_number = data.get("tracking_number")
            logger.info(f"Adding shipment: {tracking_number}")

            if Shipment.query.filter_by(tracking_number=tracking_number, user_id=current_user.id).first():
                logger.warning(f"Shipment {tracking_number} already exists")
                return jsonify({"message": "Shipment already exists"}), 400
            
            # Get tracking info from Ship24 (now using the fixed method)
            shipengine_api_start_time = time.time()
            tracking_info = shipengine.get_tracking_info(tracking_number)
            shipengine_api_end_time = time.time()
            logger.info(f"ShipEngine API call took {shipengine_api_end_time - shipengine_api_start_time:.4f}s")
            
            if not tracking_info:
                logger.error(f"Failed to get tracking info for {tracking_number}")
                return jsonify({"message": "Failed to retrieve tracking information"}), 500

            # Parse estimated delivery date
            estimated_delivery = None
            if tracking_info.get("estimated_delivery"):
                try:
                    # Handle UTC timezone format
                    est_delivery_str = tracking_info["estimated_delivery"].replace('Z', '+00:00')
                    estimated_delivery = datetime.fromisoformat(est_delivery_str)
                except Exception as e:
                    logger.warning(f"Could not parse estimated delivery: {e}")

            # Create shipment with parsed data
            db_add_start_time = time.time()
            shipment = Shipment(
                tracking_number=tracking_number,
                carrier=tracking_info.get("carrier", "Unknown"),
                status=tracking_info.get("status", "Pending"),
                origin=tracking_info.get("origin"),
                destination=tracking_info.get("destination"),
                estimated_delivery=estimated_delivery,
                user_id=current_user.id
            )
            db.session.add(shipment)
            db.session.commit()
            db_add_end_time = time.time()
            logger.info(f"DB commit took {db_add_end_time - db_add_start_time:.4f}s")
            
            # Emit real-time update for new shipment
            emit_shipment_update(current_user.id, shipment.serialize(), 'new_shipment')

            end_time = time.time()
            logger.info(f"Total time to add shipment: {end_time - start_time:.4f}s")
            return jsonify({
                "message": "Shipment added successfully",
                "shipment": shipment.serialize()
            }), 201
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding shipment: {e}")
            return jsonify({"message": "Internal server error", "details": str(e)}), 500

@app.route("/api/track/<tracking_number>", methods=["GET"])
@token_required
@cross_origin()
def track_shipment_endpoint(current_user, tracking_number):
    logger.info(f"Tracking shipment: {tracking_number} for user {current_user.username}")
    try:
        # Find shipment in database
        shipment = Shipment.query.filter_by(
            tracking_number=tracking_number,
            user_id=current_user.id
        ).first()
        
        if not shipment:
            logger.warning(f"Shipment {tracking_number} not found")
            return jsonify({"message": "Shipment not found"}), 404
        
        # Get updated tracking info (now using the fixed method)
        tracking_info = shipengine.get_tracking_info(tracking_number)
        
        # If we get new info, update shipment
        update_success = False
        status_changed = False
        old_status = shipment.status
        
        if tracking_info:
            try:
                # Update fields with new data
                new_status = tracking_info.get("status", shipment.status)
                if new_status != old_status:
                    status_changed = True
                    
                shipment.status = new_status
                shipment.carrier = tracking_info.get("carrier", shipment.carrier)
                shipment.origin = tracking_info.get("origin", shipment.origin)
                shipment.destination = tracking_info.get("destination", shipment.destination)
                
                # Update estimated delivery if available
                if tracking_info.get("estimated_delivery"):
                    try:
                        est_delivery_str = tracking_info["estimated_delivery"].replace('Z', '+00:00')
                        shipment.estimated_delivery = datetime.fromisoformat(est_delivery_str)
                    except Exception as e:
                        logger.warning(f"Error parsing delivery date: {e}")
                
                shipment.updated_at = datetime.utcnow()
                db.session.commit()
                update_success = True
                logger.info(f"Shipment {tracking_number} updated successfully")
                
                # Emit real-time update if status changed
                if status_changed:
                    emit_shipment_update(current_user.id, shipment.serialize(), 'status_change')
                    logger.info(f"Status changed from {old_status} to {new_status} - WebSocket update sent")
                    
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating shipment: {e}")
        
        # Return updated shipment info
        return jsonify({
            "message": "Tracking information retrieved",
            "updated": update_success,
            "status_changed": status_changed,
            "shipment": shipment.serialize()
        }), 200
            
    except Exception as e:
        logger.error(f"Tracking error: {e}")
        return jsonify({"message": "Internal server error", "details": str(e)}), 500

@app.route("/api/refresh-shipments", methods=["POST"])
@token_required
@cross_origin()
def refresh_shipments(current_user):
    """Manually refresh all shipments for a user"""
    logger.info(f"Manual shipment refresh requested by user {current_user.username}")
    
    try:
        # Get all active shipments for the user
        shipments = Shipment.query.filter_by(user_id=current_user.id).all()
        updated_count = 0
        status_changes = []
        
        for shipment in shipments:
            try:
                # Skip if already delivered
                if shipment.status and shipment.status.lower() in ['delivered', 'exception']:
                    continue
                
                # Get updated tracking info
                tracking_info = shipengine.get_tracking_info(shipment.tracking_number)
                
                if tracking_info:
                    old_status = shipment.status
                    new_status = tracking_info.get("status", shipment.status)
                    
                    # Update shipment data
                    shipment.status = new_status
                    shipment.carrier = tracking_info.get("carrier", shipment.carrier)
                    shipment.origin = tracking_info.get("origin", shipment.origin)
                    shipment.destination = tracking_info.get("destination", shipment.destination)
                    
                    # Update estimated delivery if available
                    if tracking_info.get("estimated_delivery"):
                        try:
                            est_delivery_str = tracking_info["estimated_delivery"].replace('Z', '+00:00')
                            shipment.estimated_delivery = datetime.fromisoformat(est_delivery_str)
                        except Exception as e:
                            logger.warning(f"Error parsing delivery date: {e}")
                    
                    shipment.updated_at = datetime.utcnow()
                    updated_count += 1
                    
                    # Track status changes
                    if new_status != old_status:
                        status_changes.append({
                            'tracking_number': shipment.tracking_number,
                            'old_status': old_status,
                            'new_status': new_status
                        })
                        
                        # Emit real-time update
                        emit_shipment_update(
                            current_user.id, 
                            shipment.serialize(), 
                            'manual_refresh'
                        )
                
            except Exception as e:
                logger.error(f"Error refreshing shipment {shipment.tracking_number}: {e}")
                continue
        
        # Commit all changes
        db.session.commit()
        
        return jsonify({
            "message": "Shipments refreshed successfully",
            "updated_count": updated_count,
            "status_changes": status_changes,
            "total_shipments": len(shipments)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error refreshing shipments: {e}")
        return jsonify({"message": "Internal server error", "details": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
@token_required
@cross_origin()
def chat(current_user):
    logger.info(f"Chat request from user {current_user.username}")
    try:
        data = request.get_json()
        message = data.get("message")
        
        if not message:
            return jsonify({"message": "Message is required"}), 400
        
        # Get user's current shipments with detailed information
        shipments = Shipment.query.filter_by(user_id=current_user.id).all()
        
        # Create detailed shipment context
        shipments_context = []
        shipment_data = {}
        for s in shipments:
            status_info = f"Tracking: {s.tracking_number}, Carrier: {s.carrier or 'Unknown'}, Status: {s.status or 'Unknown'}"
            if s.origin:
                status_info += f", From: {s.origin}"
            if s.destination:
                status_info += f", To: {s.destination}"
            if s.estimated_delivery:
                status_info += f", Est. Delivery: {s.estimated_delivery.strftime('%Y-%m-%d')}"
            
            shipments_context.append(status_info)
            shipment_data[s.tracking_number] = s.serialize()
        
        # Retrieve recent conversation history (last 10 conversations)
        conversation_history = Conversation.query.filter_by(user_id=current_user.id) \
            .order_by(Conversation.timestamp.desc()) \
            .limit(10) \
            .all()
        
        # Convert to format expected by AI
        history_data = []
        for conv in reversed(conversation_history):  # Reverse to get chronological order
            history_data.append({
                'user_message': conv.user_message,
                'ai_response': conv.ai_response,
                'timestamp': conv.timestamp.isoformat()
            })
        
        # Generate AI response with conversation history and shipment context
        ai_response = ai_assistant.generate_response(
            message, 
            shipments_context, 
            conversation_history=history_data
        )
        
        # Save conversation to database
        conversation = Conversation(
            user_message=message,
            ai_response=ai_response,
            user_id=current_user.id,
            shipment_context=shipment_data  # Store current shipment state
        )
        db.session.add(conversation)
        db.session.commit()
        
        logger.info(f"Conversation saved for user {current_user.username}")
        
        return jsonify({
            "response": ai_response,
            "conversation_id": conversation.id,
            "shipments_count": len(shipments)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Chat error: {e}")
        return jsonify({"message": str(e)}), 500

@app.route("/api/conversations", methods=["GET"])
@token_required
@cross_origin()
def get_conversations(current_user):
    """Get conversation history for the current user"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)  # Max 100 per page
        
        conversations = Conversation.query.filter_by(user_id=current_user.id) \
            .order_by(Conversation.timestamp.desc()) \
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            "conversations": [conv.serialize() for conv in conversations.items],
            "total": conversations.total,
            "page": page,
            "per_page": per_page,
            "has_more": conversations.has_next
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return jsonify({"message": str(e)}), 500

@app.route("/api/conversations/clear", methods=["POST"])
@token_required
@cross_origin()
def clear_conversations(current_user):
    """Clear all conversation history for the current user"""
    try:
        deleted_count = Conversation.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        logger.info(f"Cleared {deleted_count} conversations for user {current_user.username}")
        
        return jsonify({
            "message": "Conversation history cleared successfully",
            "deleted_count": deleted_count
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error clearing conversations: {e}")
        return jsonify({"message": str(e)}), 500

@app.route("/api/conversations/stats", methods=["GET"])
@token_required
@cross_origin()
def get_conversation_stats(current_user):
    """Get conversation statistics for the current user"""
    try:
        total_conversations = Conversation.query.filter_by(user_id=current_user.id).count()
        
        # Get recent conversation (last 7 days)
        from datetime import timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_conversations = Conversation.query.filter(
            Conversation.user_id == current_user.id,
            Conversation.timestamp >= week_ago
        ).count()
        
        # Get latest conversation
        latest_conversation = Conversation.query.filter_by(user_id=current_user.id) \
            .order_by(Conversation.timestamp.desc()) \
            .first()
        
        return jsonify({
            "total_conversations": total_conversations,
            "recent_conversations": recent_conversations,
            "latest_conversation": latest_conversation.serialize() if latest_conversation else None
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting conversation stats: {e}")
        return jsonify({"message": str(e)}), 500

# Database initialization
tables_created = False
@app.before_request
def create_tables_once():
    global tables_created
    if not tables_created:
        try:
            db.create_all()
            logger.info("Database tables created")
            tables_created = True
        except Exception as e:
            logger.error(f"Error creating tables: {str(e)}")

# Background shipment monitoring
def start_shipment_monitoring():
    """Start background monitoring for shipment status updates"""
    def monitor():
        # Configurable polling interval (in seconds)
        polling_interval = int(os.environ.get("SHIPMENT_POLLING_INTERVAL", 900))  # Default 15 minutes
        logger.info(f"Starting shipment monitoring with {polling_interval}s interval")
        
        while True:
            try:
                # Check all shipments that haven't been delivered yet
                with app.app_context():
                    # Get shipments that are not delivered (handle None status as well)
                    active_shipments = Shipment.query.filter(
                        db.or_(
                            Shipment.status.is_(None),
                            ~Shipment.status.in_(['Delivered', 'delivered', 'DELIVERED', 'Delivered', 'Exception'])
                        )
                    ).all()
                    
                    logger.info(f"Monitoring {len(active_shipments)} active shipments")
                    
                    for shipment in active_shipments:
                        try:
                            # Get updated tracking info
                            tracking_info = shipengine.get_tracking_info(shipment.tracking_number)
                            
                            if tracking_info:
                                old_status = shipment.status
                                new_status = tracking_info.get("status", shipment.status)
                                
                                # Check if status changed
                                if new_status != old_status:
                                    logger.info(f"Status change detected for {shipment.tracking_number}: {old_status} → {new_status}")
                                    
                                    # Update shipment in database
                                    shipment.status = new_status
                                    shipment.carrier = tracking_info.get("carrier", shipment.carrier)
                                    shipment.origin = tracking_info.get("origin", shipment.origin)
                                    shipment.destination = tracking_info.get("destination", shipment.destination)
                                    
                                    # Update estimated delivery if available
                                    if tracking_info.get("estimated_delivery"):
                                        try:
                                            est_delivery_str = tracking_info["estimated_delivery"].replace('Z', '+00:00')
                                            shipment.estimated_delivery = datetime.fromisoformat(est_delivery_str)
                                        except Exception as e:
                                            logger.warning(f"Error parsing delivery date: {e}")
                                    
                                    shipment.updated_at = datetime.utcnow()
                                    db.session.commit()
                                    
                                    # Emit real-time update via WebSocket
                                    emit_shipment_update(
                                        shipment.user_id, 
                                        shipment.serialize(), 
                                        'status_change_auto'
                                    )
                                    
                                    logger.info(f"Updated shipment {shipment.tracking_number} and sent WebSocket notification")
                            
                            # Small delay between requests to avoid rate limiting
                            time.sleep(2)
                            
                        except Exception as e:
                            logger.error(f"Error monitoring shipment {shipment.tracking_number}: {e}")
                            continue
                    
                # Wait for next polling cycle
                logger.info(f"Shipment monitoring cycle complete. Next check in {polling_interval}s")
                time.sleep(polling_interval)
                
            except Exception as e:
                logger.error(f"Shipment monitoring error: {e}")
                # Wait a bit before retrying
                time.sleep(60)
    
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    logger.info("Shipment monitoring service started")

# Background email monitoring (kept for future use)
def start_email_monitoring():
    def monitor():
        while True:
            try:
                logger.info("Email monitoring active")
                # Actual implementation would go here
                time.sleep(300)  # Check every 5 minutes
            except Exception as e:
                logger.error(f"Email monitoring error: {e}")
                time.sleep(600)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

if __name__ == "__main__":
    # Enhanced API key validation on startup
    if not SHIPENGINE_API_KEY:
        logger.warning("SHIPENGINE_API_KEY not set - tracking will fail")
    else:
        # Test API key validity on startup
        if shipengine.validate_api_key():
            logger.info("ShipEngine API key validated successfully")
        else:
            logger.error("ShipEngine API key validation failed")
            
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set - AI features will fail")
    
    with app.app_context():
        db.create_all()
    start_shipment_monitoring()
    start_email_monitoring()
    
    # Run with SocketIO support
    socketio.run(app, debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))