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

# Ship24 API Integration
class Ship24API:
    def __init__(self):
        self.api_key = SHIP24_API_KEY
        self.base_url = "https://api.ship24.com/public/v1"  # Fixed: removed extra space
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def track_shipment(self, tracking_number):
        logger.info(f"Attempting to track shipment: {tracking_number} via Ship24 API.")
        url = f"{self.base_url}/trackers/track"
        payload = {"trackingNumber": tracking_number}
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            logger.info(f"Ship24 track_shipment response: {response.status_code}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error tracking shipment {tracking_number} with Ship24: {e}")
            return None

    def get_tracking_info(self, tracking_number):
        logger.info(f"Attempting to get tracking info for: {tracking_number} via Ship24 API.")
        url = f"{self.base_url}/trackers/search"
        params = {"trackingNumbers": tracking_number}
        try:
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            logger.info(f"Ship24 get_tracking_info response: {response.status_code}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting tracking info for {tracking_number} with Ship24: {e}")
            return None

ship24 = Ship24API()

# OpenAI Integration
class LogisticsAI:
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)

    def generate_response(self, user_message, user_shipments=None, context=None):
        system_prompt = """You are a helpful AI assistant for a logistics company."""
        if user_shipments:
            system_prompt += f"\nUser's current shipments: {user_shipments}"
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
        if not data:  # Fixed: completed the if statement
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
            return jsonify({"shipments": [{
                "id": s.id,
                "tracking_number": s.tracking_number,
                "carrier": s.carrier,
                "description": s.description,
                "origin": s.origin,
                "destination": s.destination,
                "status": s.status,
                "estimated_delivery": s.estimated_delivery.isoformat() if s.estimated_delivery else None,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat()
            } for s in shipments]}), 200
        except Exception as e:
            logger.error(f"Error retrieving shipments for user {current_user.username}: {e}")
            return jsonify({"message": str(e)}), 500
    elif request.method == "POST":
        logger.info(f"POST /api/shipments called by user {current_user.username}.")
        start_time = time.time()
        try:
            data = request.get_json()
            tracking_number = data.get("tracking_number")
            logger.info(f"Received request to add tracking number: {tracking_number}.")

            if Shipment.query.filter_by(tracking_number=tracking_number, user_id=current_user.id).first():
                logger.warning(f"Shipment {tracking_number} already exists for user {current_user.username}.")
                return jsonify({"message": "Shipment already exists"}), 400
            
            # Step 1: Call Ship24 API
            ship24_api_start_time = time.time()
            tracking_info = ship24.get_tracking_info(tracking_number)
            ship24_api_end_time = time.time()
            logger.info(f"Ship24 API call for {tracking_number} took {ship24_api_end_time - ship24_api_start_time:.4f} seconds.")

            if not tracking_info:
                logger.error(f"Failed to get tracking info from Ship24 for {tracking_number}.")
                return jsonify({"message": "Failed to retrieve tracking information from Ship24"}), 500

            # Step 2: Create Shipment object and add to DB
            db_add_start_time = time.time()
            shipment = Shipment(
                tracking_number=tracking_number,
                carrier=tracking_info.get("carrier") if tracking_info else "Unknown",
                status="Processing",
                user_id=current_user.id
            )
            db.session.add(shipment)
            db.session.commit()
            db_add_end_time = time.time()
            logger.info(f"Database add and commit for {tracking_number} took {db_add_end_time - db_add_start_time:.4f} seconds.")

            end_time = time.time()
            logger.info(f"Total time to add shipment {tracking_number}: {end_time - start_time:.4f} seconds.")
            return jsonify({"message": "Shipment added successfully"}), 201
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding shipment for user {current_user.username}: {e}")
            return jsonify({"message": "Internal server error", "details": str(e)}), 500

# Added missing track endpoint
@app.route("/api/track/<tracking_number>", methods=["GET"])
@token_required
@cross_origin()
def track_shipment_endpoint(current_user, tracking_number):
    logger.info(f"GET /api/track/{tracking_number} called by user {current_user.username}.")
    try:
        # Find the shipment in the database
        db_query_start_time = time.time()
        shipment = Shipment.query.filter_by(
            tracking_number=tracking_number,
            user_id=current_user.id
        ).first()
        db_query_end_time = time.time()
        logger.info(f"Database query for shipment {tracking_number} took {db_query_end_time - db_query_start_time:.4f} seconds.")
        
        if not shipment:
            logger.warning(f"Shipment {tracking_number} not found for user {current_user.username}.")
            return jsonify({"message": "Shipment not found"}), 404
        
        # Get updated tracking info from Ship24
        ship24_api_start_time = time.time()
        tracking_info = ship24.get_tracking_info(tracking_number)
        ship24_api_end_time = time.time()
        logger.info(f"Ship24 API call for {tracking_number} took {ship24_api_end_time - ship24_api_start_time:.4f} seconds.")
        
        if tracking_info:
            # Update shipment with new information
            db_update_start_time = time.time()
            shipment.status = tracking_info.get("status", shipment.status)
            shipment.carrier = tracking_info.get("carrier", shipment.carrier)
            shipment.origin = tracking_info.get("origin", shipment.origin)
            shipment.destination = tracking_info.get("destination", shipment.destination)
            shipment.updated_at = datetime.utcnow()
            
            if tracking_info.get("estimated_delivery"):
                try:
                    shipment.estimated_delivery = datetime.fromisoformat(tracking_info["estimated_delivery"])
                except:
                    logger.warning(f"Could not parse estimated_delivery for {tracking_number}: {tracking_info['estimated_delivery']}")
                    pass
            
            db.session.commit()
            db_update_end_time = time.time()
            logger.info(f"Database update and commit for {tracking_number} took {db_update_end_time - db_update_start_time:.4f} seconds.")
            
            return jsonify({
                "message": "Tracking information updated successfully",
                "shipment": {
                    "id": shipment.id,
                    "tracking_number": shipment.tracking_number,
                    "carrier": shipment.carrier,
                    "status": shipment.status,
                    "origin": shipment.origin,
                    "destination": shipment.destination,
                    "estimated_delivery": shipment.estimated_delivery.isoformat() if shipment.estimated_delivery else None,
                    "updated_at": shipment.updated_at.isoformat()
                }
            }), 200
        else:
            logger.error(f"Unable to fetch tracking information from Ship24 for {tracking_number}.")
            return jsonify({"message": "Unable to fetch tracking information"}), 502
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in track_shipment_endpoint for {tracking_number}: {e}")
        return jsonify({"message": "Internal server error", "details": str(e)}), 500

@app.route("/api/chat", methods=["POST"])
@token_required
@cross_origin()
def chat(current_user):
    logger.info(f"POST /api/chat called by user {current_user.username}.")
    try:
        data = request.get_json()
        message = data.get("message")
        shipments = Shipment.query.filter_by(user_id=current_user.id).all()
        shipments_context = [f"{s.tracking_number} ({s.status})" for s in shipments]
        ai_response = ai_assistant.generate_response(message, shipments_context)
        logger.info("AI chat response sent.")
        return jsonify({"response": ai_response}), 200
    except Exception as e:
        logger.error(f"Error in chat endpoint for user {current_user.username}: {e}")
        return jsonify({"message": str(e)}), 500

# Fix for Flask v2.3+ (no before_first_request)
tables_created = False
@app.before_request
def create_tables_once():
    global tables_created
    if not tables_created:
        try:
            db.create_all()
            logger.info("Database tables created successfully.")
            tables_created = True
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")

# Background email monitoring
def start_email_monitoring():
    def monitor():
        while True:
            try:
                logger.info("Email monitoring thread started.")
                # Simulate email monitoring
                time.sleep(60)
            except Exception as e:
                logger.error(f"Email monitoring error: {e}")
                time.sleep(300)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    start_email_monitoring()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

