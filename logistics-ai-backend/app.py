import logging
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
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

# API Keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SHIP24_API_KEY = os.environ.get("SHIP24_API_KEY")
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

# FIXED Ship24 API Integration - Updated with correct endpoints and error handling
class Ship24API:
    def __init__(self):
        self.api_key = SHIP24_API_KEY
        self.base_url = "https://api.ship24.com/public/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Validate API key on initialization
        if not self.api_key:
            logger.error("SHIP24_API_KEY not set - tracking will fail")
    
    def _parse_ship24_response(self, api_response):
        """Parse Ship24 API response and extract tracking information"""
        try:
            if not api_response or not api_response.get('data'):
                logger.warning("No data in Ship24 response")
                return None
                
            trackings = api_response['data'].get('trackings', [])
            if not trackings:
                logger.warning("No trackings found in Ship24 response")
                return None
                
            # Get the first tracking result
            shipment_track = trackings[0].get('shipmentTrack', [{}])[0]
            
            # Extract carrier and status
            carrier = shipment_track.get('carrier', {}).get('name', 'Unknown')
            status = shipment_track.get('status', 'Unknown')
            
            # Extract origin/destination
            origin_addr = shipment_track.get('shipment', {}).get('origin', {}).get('address', {})
            origin = f"{origin_addr.get('city', '')}, {origin_addr.get('country', '')}" if origin_addr else None
            
            dest_addr = shipment_track.get('shipment', {}).get('destination', {}).get('address', {})
            destination = f"{dest_addr.get('city', '')}, {dest_addr.get('country', '')}" if dest_addr else None
            
            # Extract estimated delivery
            estimated_delivery = shipment_track.get('shipment', {}).get('estimatedDeliveryDate')
            
            return {
                "carrier": carrier,
                "status": status,
                "origin": origin,
                "destination": destination,
                "estimated_delivery": estimated_delivery
            }
        except Exception as e:
            logger.error(f"Error parsing Ship24 response: {e}")
            return None

    def track_shipment(self, tracking_number):
        """
        Create tracker and get tracking results in one call.
        Enhanced with better error handling and timeout.
        """
        logger.info(f"Tracking shipment: {tracking_number} via Ship24 API.")
        url = f"{self.base_url}/trackers/track"
        payload = {"trackingNumber": tracking_number}
        
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=30)
            response.raise_for_status()
            logger.info(f"Ship24 track_shipment response: {response.status_code}")
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.error(f"Ship24 API: Tracking number {tracking_number} not found")
            elif e.response.status_code == 401:
                logger.error("Ship24 API: Invalid API key or authentication failed")
            elif e.response.status_code == 422:
                logger.error(f"Ship24 API: Invalid tracking number format: {tracking_number}")
            else:
                logger.error(f"Ship24 API HTTP error {e.response.status_code}: {e}")
            return None
            
        except requests.exceptions.Timeout:
            logger.error(f"Ship24 API timeout for tracking number: {tracking_number}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ship24 API network error: {e}")
            return None

    def get_tracking_info(self, tracking_number):
        """
        FIXED METHOD: Uses the correct Ship24 API approach.
        Instead of using the non-existent /trackers/results endpoint,
        this reuses the track_shipment method which uses the correct endpoint.
        """
        logger.info(f"Fetching tracking info for: {tracking_number}")
        
        try:
            # Use the track_shipment method which calls the correct endpoint
            api_response = self.track_shipment(tracking_number)
            
            # Handle None response (error cases)
            if api_response is None:
                logger.error(f"Failed to get tracking info for {tracking_number}")
                return None
            
            # Parse the successful response
            parsed_data = self._parse_ship24_response(api_response)
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
            
        url = f"{self.base_url}/couriers"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                logger.info("Ship24 API key validation successful")
                return True
            elif response.status_code == 401:
                logger.error("Ship24 API key validation failed: Invalid key")
                return False
            else:
                logger.warning(f"Ship24 API key validation returned {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error validating Ship24 API key: {e}")
            return False

ship24 = Ship24API()

# OpenAI Integration
class LogisticsAI:
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

    def generate_response(self, user_message, user_shipments=None, context=None):
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
- Provide actionable advice and clear explanations
- Be empathetic when dealing with delivery issues or concerns

Always prioritize helping users with their shipping and logistics needs."""
        if user_shipments:
            system_prompt += f"\n\nUser's current shipments: {user_shipments}"
        if context:
            system_prompt += f"\nAdditional context: {context}"
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
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
            ship24_api_start_time = time.time()
            tracking_info = ship24.get_tracking_info(tracking_number)
            ship24_api_end_time = time.time()
            logger.info(f"Ship24 API call took {ship24_api_end_time - ship24_api_start_time:.4f}s")
            
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
        tracking_info = ship24.get_tracking_info(tracking_number)
        
        # If we get new info, update shipment
        update_success = False
        if tracking_info:
            try:
                # Update fields with new data
                shipment.status = tracking_info.get("status", shipment.status)
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
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error updating shipment: {e}")
        
        # Return updated shipment info
        return jsonify({
            "message": "Tracking information retrieved",
            "updated": update_success,
            "shipment": shipment.serialize()
        }), 200
            
    except Exception as e:
        logger.error(f"Tracking error: {e}")
        return jsonify({"message": "Internal server error", "details": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
@token_required
@cross_origin()
def chat(current_user):
    logger.info(f"Chat request from user {current_user.username}")
    try:
        data = request.get_json()
        message = data.get("message")
        shipments = Shipment.query.filter_by(user_id=current_user.id).all()
        shipments_context = [f"{s.tracking_number} ({s.status})" for s in shipments]
        ai_response = ai_assistant.generate_response(message, shipments_context)
        return jsonify({"response": ai_response}), 200
    except Exception as e:
        logger.error(f"Chat error: {e}")
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

# Background email monitoring
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
    if not SHIP24_API_KEY:
        logger.warning("SHIP24_API_KEY not set - tracking will fail")
    else:
        # Test API key validity on startup
        if ship24.validate_api_key():
            logger.info("Ship24 API key validated successfully")
        else:
            logger.error("Ship24 API key validation failed")
            
    if not OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set - AI features will fail")
    
    with app.app_context():
        db.create_all()
    start_email_monitoring()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))