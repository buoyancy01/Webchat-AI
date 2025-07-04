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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///logistics.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['IMAP_SERVER'] = os.environ.get('IMAP_SERVER', 'imap.gmail.com')

CORS(app, origins=['*'])
db = SQLAlchemy(app)
mail = Mail(app)

# API Keys
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
SHIP24_API_KEY = os.environ.get('SHIP24_API_KEY')

openai.api_key = OPENAI_API_KEY

# Database Models
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

# JWT Token decorator
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

# Ship24 API Integration
class Ship24API:
    def __init__(self):
        self.api_key = SHIP24_API_KEY
        self.base_url = "https://api.ship24.com/public/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def track_shipment(self, tracking_number):
        try:
            url = f"{self.base_url}/trackers/track"
            payload = {
                "trackingNumber": tracking_number
            }
            response = requests.post(url, json=payload, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Ship24 API Error: {e}")
            return None
    
    def get_tracking_info(self, tracking_number):
        try:
            url = f"{self.base_url}/trackers/search"
            params = {"trackingNumbers": tracking_number}
            response = requests.get(url, params=params, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            print(f"Ship24 API Error: {e}")
            return None

ship24 = Ship24API()

# OpenAI Integration
class LogisticsAI:
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    def generate_response(self, user_message, user_shipments=None, context=None):
        system_prompt = """You are a helpful AI assistant for a logistics company. 
        Your role is to help clients with their shipment inquiries in a friendly and professional manner.
        You can:
        1. Answer questions about shipment status
        2. Provide tracking information
        3. Help with general logistics questions
        4. Assist with shipment-related concerns
        
        Be conversational, helpful, and always maintain a professional tone.
        If you need specific tracking information, ask for the tracking number.
        """
        
        if user_shipments:
            system_prompt += f"\n\nUser's current shipments: {user_shipments}"
        
        if context:
            system_prompt += f"\n\nAdditional context: {context}"
        
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

# Email Processing
class EmailProcessor:
    def __init__(self):
        self.imap_server = app.config['IMAP_SERVER']
        self.email_user = app.config['MAIL_USERNAME']
        self.email_pass = app.config['MAIL_PASSWORD']
    
    def extract_tracking_numbers(self, text):
        # Common tracking number patterns
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
            # Extract tracking numbers
            tracking_numbers = self.extract_tracking_numbers(email_content)
            
            # Find user
            user = User.query.filter_by(email=user_email).first()
            if not user:
                return False
            
            # Process each tracking number
            for tracking_num in tracking_numbers:
                # Check if shipment already exists
                existing = Shipment.query.filter_by(
                    tracking_number=tracking_num, 
                    user_id=user.id
                ).first()
                
                if not existing:
                    # Get tracking info from Ship24
                    tracking_info = ship24.get_tracking_info(tracking_num)
                    
                    # Create new shipment
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
            print(f"Email processing error: {e}")
            return False
    
    def monitor_emails(self):
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server)
            mail.login(self.email_user, self.email_pass)
            mail.select('inbox')
            
            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')
            
            for msg_id in messages[0].split():
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                email_msg = email.message_from_bytes(msg_data[0][1])
                
                # Get email content
                if email_msg.is_multipart():
                    for part in email_msg.walk():
                        if part.get_content_type() == "text/plain":
                            content = part.get_payload(decode=True).decode()
                            break
                else:
                    content = email_msg.get_payload(decode=True).decode()
                
                # Process email
                sender = email_msg['From']
                self.process_shipment_email(content, sender)
                
                # Mark as read
                mail.store(msg_id, '+FLAGS', '\\Seen')
            
            mail.close()
            mail.logout()
        except Exception as e:
            print(f"Email monitoring error: {e}")

email_processor = EmailProcessor()

# Routes
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        company_name = data.get("company_name")
        
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
        return jsonify({'message': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            token = jwt.encode({
                'user_id': user.id,
                'exp': datetime.utcnow() + timedelta(days=7)
            }, app.config['SECRET_KEY'])
            
            return jsonify({
                'token': token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'company_name': user.company_name
                }
            }), 200
        
        return jsonify({'message': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/shipments', methods=['GET'])
@token_required
def get_shipments(current_user):
    try:
        shipments = Shipment.query.filter_by(user_id=current_user.id).all()
        shipments_data = []
        
        for shipment in shipments:
            shipments_data.append({
                'id': shipment.id,
                'tracking_number': shipment.tracking_number,
                'carrier': shipment.carrier,
                'description': shipment.description,
                'origin': shipment.origin,
                'destination': shipment.destination,
                'status': shipment.status,
                'estimated_delivery': shipment.estimated_delivery.isoformat() if shipment.estimated_delivery else None,
                'created_at': shipment.created_at.isoformat(),
                'updated_at': shipment.updated_at.isoformat()
            })
        
        return jsonify({'shipments': shipments_data}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/track/<tracking_number>', methods=['GET'])
@token_required
def track_shipment(current_user, tracking_number):
    try:
        # Get tracking info from Ship24
        tracking_info = ship24.get_tracking_info(tracking_number)
        
        if tracking_info:
            # Update local database
            shipment = Shipment.query.filter_by(
                tracking_number=tracking_number,
                user_id=current_user.id
            ).first()
            
            if shipment:
                shipment.status = tracking_info.get('status', shipment.status)
                shipment.updated_at = datetime.utcnow()
                db.session.commit()
        
        return jsonify({'tracking_info': tracking_info}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
@token_required
def chat(current_user):
    try:
        data = request.get_json()
        message = data.get('message')
        
        # Get user's shipments for context
        shipments = Shipment.query.filter_by(user_id=current_user.id).all()
        shipments_context = [
            f"Tracking: {s.tracking_number}, Status: {s.status}, Carrier: {s.carrier}"
            for s in shipments
        ]
        
        # Generate AI response
        ai_response = ai_assistant.generate_response(
            message, 
            shipments_context,
            f"User: {current_user.username}"
        )
        
        return jsonify({'response': ai_response}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/shipments', methods=['POST'])
@token_required
def add_shipment(current_user):
    try:
        data = request.get_json()
        tracking_number = data.get('tracking_number')
        description = data.get('description', '')
        
        # Check if shipment already exists
        existing = Shipment.query.filter_by(
            tracking_number=tracking_number,
            user_id=current_user.id
        ).first()
        
        if existing:
            return jsonify({'message': 'Shipment already exists'}), 400
        
        # Get initial tracking info
        tracking_info = ship24.get_tracking_info(tracking_number)
        
        shipment = Shipment(
            tracking_number=tracking_number,
            description=description,
            carrier=tracking_info.get('carrier') if tracking_info else 'Unknown',
            status=tracking_info.get('status') if tracking_info else 'Processing',
            user_id=current_user.id
        )
        
        db.session.add(shipment)
        db.session.commit()
        
        return jsonify({'message': 'Shipment added successfully'}), 201
    except Exception as e:
        return jsonify({'message': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200

# Background email monitoring
def start_email_monitoring():
    def monitor():
        while True:
            try:
                email_processor.monitor_emails()
                time.sleep(60)  # Check every minute
            except Exception as e:
                print(f"Email monitoring error: {e}")
                time.sleep(300)  # Wait 5 minutes on error
    
    if app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD']:
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Start email monitoring in production
    if os.environ.get('FLASK_ENV') != 'development':
        start_email_monitoring()
    
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))