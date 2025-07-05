from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin  # Required for explicit CORS control
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import openai
import requests
import os
import jwt
from datetime import datetime, timedelta
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Use PostgreSQL from Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///logistics_production.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": ["Authorization", "Content-Type"]}}, supports_credentials=True)
db = SQLAlchemy(app)

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

class Shipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tracking_number = db.Column(db.String(100), nullable=False)
    carrier = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# JWT Token decorator with OPTIONS bypass
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)  # Skip token check for preflight
            
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        try:
            token = token.replace('Bearer ', '')
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
        except Exception as e:
            app.logger.error(f"JWT Error: {str(e)}")
            return jsonify({'message': 'Token is invalid or expired'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

# Ship24 API Integration (fixed URL typo)
class Ship24API:
    def __init__(self):
        self.api_key = SHIP24_API_KEY
        self.base_url = "https://api.ship24.com/public/v1 "  # Fixed URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    def get_tracking_info(self, tracking_number):
        try:
            url = f"{self.base_url}/trackers/search"
            response = requests.get(url, params={"trackingNumbers": tracking_number}, headers=self.headers)
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            app.logger.error(f"Ship24 API Error: {e}")
            return None
ship24 = Ship24API()

# OpenAI Integration
class LogisticsAI:
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
    def generate_response(self, user_message):
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a logistics assistant"},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"
ai_assistant = LogisticsAI()

# Registration Route with JSON validation
@app.route('/api/register', methods=['POST'])
@cross_origin()
def register():
    try:
        if not request.is_json:
            return jsonify({'message': 'Invalid Content-Type: JSON required'}), 400
            
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not all([username, email, password]):
            return jsonify({'message': 'Missing required fields'}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({'message': 'Username already exists'}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({'message': 'Email already exists'}), 400

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        return jsonify({'message': 'User created successfully'}), 201

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Registration error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

# Login Route
@app.route('/api/login', methods=['POST'])
@cross_origin()
def login():
    try:
        if not request.is_json:
            return jsonify({'message': 'Invalid Content-Type: JSON required'}), 400
            
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not all([username, password]):
            return jsonify({'message': 'Missing username or password'}), 400

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
                    'email': user.email
                }
            }), 200
        return jsonify({'message': 'Invalid credentials'}), 401

    except Exception as e:
        app.logger.error(f"Login error: {str(e)}")
        return jsonify({'message': 'Internal server error'}), 500

# Shipments Route
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
            app.logger.error(f"Get shipments error: {str(e)}")
            return jsonify({'message': 'Error fetching shipments'}), 500
    
    elif request.method == 'POST':
        try:
            if not request.is_json:
                return jsonify({'message': 'Invalid Content-Type: JSON required'}), 400
                
            data = request.get_json()
            tracking_number = data.get('tracking_number')
            
            if not tracking_number:
                return jsonify({'message': 'Tracking number required'}), 400
                
            if Shipment.query.filter_by(tracking_number