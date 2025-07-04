from flask import Flask, request, jsonify, session
from flask_cors import CORS
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
import logging

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Use PostgreSQL from Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///logistics_production.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['IMAP_SERVER'] = os.environ.get('IMAP_SERVER', 'imap.gmail.com')

# Setup
CORS(app, origins=['*'])
db = SQLAlchemy(app)
mail = Mail(app)

# API Keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
SHIP24_API_KEY = os.environ.get('SHIP24_API_KEY')
openai.api_key = OPENAI_API_KEY

# Set up logging
app.logger.setLevel(logging.DEBUG)

# Database Models & Classes (unchanged for brevity)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    company_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    shipments = db.relationship('Shipment', backref='user', lazy=True)

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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.Column(db.Text, nullable=True)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# JWT Token decorator (unchanged)
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        try:
            token = token.replace('Bearer ', '')
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
        except:
            return jsonify({'message': 'Token is invalid'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# Ship24 API Integration (unchanged)
class Ship24API:
    def __init__(self):
        self.api_key = SHIP24_API_KEY
        self.base_url = "https://api.ship24.com/public/v1 "
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    def track_shipment(self, tracking_number):
        try:
            url = f"{self.base_url}/trackers/track"
            payload = {"trackingNumber": tracking_number}
            response = requests.post(url, json=payload, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            app.logger.error(f"Ship24 API Error: {e}")
            return None
    def get_tracking_info(self, tracking_number):
        try:
            url = f"{self.base_url}/trackers/search"
            params = {"trackingNumbers": tracking_number}
            response = requests.get(url, params=params, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            app.logger.error(f"Ship24 API Error: {e}")
            return None
ship24 = Ship24API()

# OpenAI Integration (unchanged)
class LogisticsAI:
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
    def generate_response(self, user_message, user_shipments=None, context=None):
        system_prompt = """You are a helpful AI assistant for a logistics company..."""
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
            return response.choices[0].message.content
        except Exception as e:
            return f"I apologize, but I'm having trouble processing your request right now. Please try again later. Error: {str(e)}"
ai_assistant = LogisticsAI()

# Email Processing (unchanged)
class EmailProcessor:
    def __init__(self):
        self.imap_server = app.config['IMAP_SERVER']
        self.email_user = app.config['MAIL_USERNAME']
        self.email_pass = app.config['MAIL_PASSWORD']
    def extract_tracking_numbers(self, text):
        patterns = [
            r'\b1Z[0-9A-Z]{16}\b',  # UPS
            r'\b\d{12}\b',          # FedEx 12-digit
            r'\b\d{20}\b',          # FedEx 20-digit
            r'\b9[0-9]{21}\b',      # USPS
            r'\b[A-Z]{2}[0-9]{9}[A-Z]{2}\b',  # DHL
        ]
        tracking_numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, text)
            tracking_numbers.extend(matches)
        return list(set(tracking_numbers))  # Remove duplicates
    def process_shipment_email(self, email_content, user_email):
        try:
            tracking_numbers = self.extract_tracking_numbers(email_content)
            user = User.query.filter_by(email=user_email).first()
            if not user:
                return False
            for tracking_num in tracking_numbers:
                existing = Shipment.query.filter_by(tracking_number=tracking_num, user_id=user.id).first()
                if not existing:
                    tracking_info = ship24.get_tracking_info(tracking_num)
                    shipment = Shipment(
                        tracking_number=tracking_num,
                        carrier=tracking_info.get('carrier') if tracking_info else 'Unknown',
                        status='Processing',
                        user_id=user.id
                    )
                    db.session.add(shipment)
            db.session.commit()
            return True
        except Exception as e:
            app.logger.error(f"Email processing error: {e}")
            return False
    def monitor_emails(self):
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_user, self.email_pass)
            mail.select('inbox')
            status, messages = mail.search(None, 'UNSEEN')
            for msg_id in messages[0].split():
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                email_msg = email.message_from_bytes(msg_data[0][1])
                content = ""
                if email_msg.is_multipart():
                    for part in email_msg.walk():
                        if part.get_content_type() == "text/plain":
                            content = part.get_payload(decode=True).decode()
                            break
                else:
                    content = email_msg.get_payload(decode=True).decode()
                sender = email_msg['From']
                self.process_shipment_email(content, sender)
                mail.store(msg_id, '+FLAGS', '\\Seen')
            mail.close()
            mail.logout()
        except Exception as e:
            app.logger.error(f"Email monitoring error: {e}")
email_processor = EmailProcessor()

# Updated /register route with better error handling
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            app.logger.warning("No JSON payload received in registration")
            return jsonify({'message': 'No JSON payload received'}), 400

        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        company_name = data.get("company_name")

        if not all([username, email, password]):
            return jsonify({'message': 'Username, email, and password are required'}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({'message': 'Username already exists'}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({'message': 'Email already exists'}), 400

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            company_name=company_name
        )
        db.session.add(user)
        db.session.commit()
        return jsonify({'message': 'User created successfully'}), 201

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Registration error: {str(e)}", exc_info=True)
        return jsonify({'message': 'Internal server error', 'details': str(e)}), 500

# Other routes unchanged...

# Ensure database tables exist
@app.before_first_request
def create_tables():
    try:
        db.create_all()
        app.logger.info("Database tables created successfully")
    except Exception as e:
        app.logger.error(f"Error creating database tables: {str(e)}")

# Background email monitoring
def start_email_monitoring():
    def monitor():
        while True:
            try:
                email_processor.monitor_emails()
                time.sleep(60)  # Check every minute
            except Exception as e:
                app.logger.error(f"Email monitoring error: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    if app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD']:
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

if __name__ == '__main__':
    # Ensure tables exist
    with app.app_context():
        db.create_all()
    # Start email monitoring in production
    if os.environ.get('FLASK_ENV') != 'development':
        start_email_monitoring()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))