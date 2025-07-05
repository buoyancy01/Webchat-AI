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

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Use PostgreSQL on Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///logistics_production.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['IMAP_SERVER'] = os.environ.get('IMAP_SERVER', 'imap.gmail.com')

# Setup extensions
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": ["Authorization", "Content-Type"]}}, supports_credentials=True)
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

# JWT Token decorator (skips OPTIONS requests)
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)

        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        try:
            token = token.replace('Bearer ', '')
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
        except Exception as e:
            return jsonify({'message': str(e)}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# Ship24 API Integration (fixed base URL)
class Ship24API:
    def __init__(self):
        self.api_key = SHIP24_API_KEY
        self.base_url = "https://api.ship24.com/public/v1 "
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def track_shipment(self, tracking_number):
        url = f"{self.base_url}/trackers/track"
        payload = {"trackingNumber": tracking_number}
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json() if response.status_code == 200 else None

    def get_tracking_info(self, tracking_number):
        url = f"{self.base_url}/trackers/search"
        params = {"trackingNumbers": tracking_number}
        response = requests.get(url, params=params, headers=self.headers)
        return response.json() if response.status_code == 200 else None

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
            return response.choices[0].message.content
        except Exception as e:
            return f"I apologize, but I'm having trouble processing your request right now. Error: {str(e)}"

ai_assistant = LogisticsAI()

# Routes
@app.route('/api/register', methods=['POST'])
@cross_origin()
def register():
    try:
        data = request.get_json()
        if not 
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
        return jsonify({'message': 'Internal server error', 'details': str(e)}), 500

@app.route('/api/login', methods=['POST'])
@cross_origin()
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

@app.route('/api/shipments', methods=['GET', 'POST'])
@token_required
@cross_origin()
def handle_shipments(current_user):
    if request.method == 'GET':
        try:
            shipments = Shipment.query.filter_by(user_id=current_user.id).all()
            return jsonify({'shipments': [{
                'id': s.id,
                'tracking_number': s.tracking_number,
                'status': s.status,
                'created_at': s.created_at.isoformat()
            } for s in shipments]}), 200
        except Exception as e:
            return jsonify({'message': str(e)}), 500
    elif request.method == 'POST':
        try:
            data = request.get_json()
            tracking_number = data.get('tracking_number')
            if Shipment.query.filter_by(tracking_number=tracking_number, user_id=current_user.id).first():
                return jsonify({'message': 'Shipment already exists'}), 400
            tracking_info = ship24.get_tracking_info(tracking_number)
            shipment = Shipment(
                tracking_number=tracking_number,
                carrier=tracking_info.get('carrier') if tracking_info else 'Unknown',
                status='Processing',
                user_id=current_user.id
            )
            db.session.add(shipment)
            db.session.commit()
            return jsonify({'message': 'Shipment added successfully'}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': 'Internal server error', 'details': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
@token_required
@cross_origin()
def chat(current_user):
    try:
        data = request.get_json()
        message = data.get('message')
        shipments = Shipment.query.filter_by(user_id=current_user.id).all()
        shipments_context = [f"{s.tracking_number} ({s.status})" for s in shipments]
        ai_response = ai_assistant.generate_response(message, shipments_context)
        return jsonify({'response': ai_response}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

# Fix for Flask v2.3+ (no before_first_request)
tables_created = False
@app.before_request
def create_tables_once():
    global tables_created
    if not tables_created:
        try:
            db.create_all()
            print("Database tables created successfully")
            tables_created = True
        except Exception as e:
            print(f"Error creating database tables: {str(e)}")

# Background email monitoring
def start_email_monitoring():
    def monitor():
        while True:
            try:
                # Simulate email monitoring
                time.sleep(60)
            except Exception as e:
                print(f"Email monitoring error: {e}")
                time.sleep(300)
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    start_email_monitoring()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))