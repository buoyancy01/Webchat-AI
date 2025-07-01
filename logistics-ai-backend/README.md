# Logistics AI Backend

A Flask-based backend for the Logistics AI application that provides user authentication, shipment tracking, AI chat functionality, and email automation.

## Features

- **User Authentication**: JWT-based authentication system
- **Shipment Tracking**: Integration with Ship24 API for real-time tracking
- **AI Chat Assistant**: OpenAI-powered conversational interface
- **Email Automation**: Automatic processing of shipment emails
- **Database Management**: SQLAlchemy with PostgreSQL support
- **API Documentation**: RESTful API endpoints

## Tech Stack

- **Framework**: Flask 2.3.3
- **Database**: PostgreSQL (with SQLAlchemy ORM)
- **Authentication**: JWT tokens
- **AI**: OpenAI GPT-3.5-turbo
- **Tracking**: Ship24 API
- **Email**: Flask-Mail with IMAP monitoring
- **Deployment**: Render.com

## Prerequisites

- Python 3.8+
- PostgreSQL database
- OpenAI API key
- Ship24 API key
- Email account with IMAP access

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd logistics-ai-backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your actual values
```

5. Initialize the database:
```bash
python -c "from app import app, db; app.app_context().push(); db.create_all()"
```

6. Run the application:
```bash
python app.py
```

## Environment Variables

Create a `.env` file with the following variables:

```env
SECRET_KEY=your-super-secret-key-here
FLASK_ENV=development
DATABASE_URL=postgresql://username:password@localhost/logistics_db
OPENAI_API_KEY=your-openai-api-key-here
SHIP24_API_KEY=your-ship24-api-key-here
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
IMAP_SERVER=imap.gmail.com
```

## API Endpoints

### Authentication

#### Register User
```http
POST /api/register
Content-Type: application/json

{
  "username": "string",
  "email": "string",
  "password": "string",
  "company_name": "string" (optional)
}
```

#### Login
```http
POST /api/login
Content-Type: application/json

{
  "username": "string",
  "password": "string"
}
```

### Shipments

#### Get All Shipments
```http
GET /api/shipments
Authorization: Bearer <token>
```

#### Add New Shipment
```http
POST /api/shipments
Authorization: Bearer <token>
Content-Type: application/json

{
  "tracking_number": "string",
  "description": "string" (optional)
}
```

#### Track Specific Shipment
```http
GET /api/track/<tracking_number>
Authorization: Bearer <token>
```

### AI Chat

#### Send Message to AI
```http
POST /api/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "string"
}
```

### Health Check

#### Check API Health
```http
GET /api/health
```

## Database Schema

### Users Table
- `id`: Primary key
- `username`: Unique username
- `email`: Unique email address
- `password_hash`: Hashed password
- `company_name`: Optional company name
- `created_at`: Registration timestamp

### Shipments Table
- `id`: Primary key
- `tracking_number`: Shipment tracking number
- `carrier`: Shipping carrier
- `description`: Shipment description
- `origin`: Origin location
- `destination`: Destination location
- `status`: Current status
- `estimated_delivery`: Expected delivery date
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp
- `user_id`: Foreign key to users table

### Chat Sessions Table
- `id`: Primary key
- `user_id`: Foreign key to users table
- `messages`: JSON string of chat history
- `created_at`: Session creation timestamp

## Email Automation

The system automatically monitors emails for shipment information:

1. **Email Monitoring**: Continuously checks for new emails
2. **Tracking Extraction**: Uses regex patterns to extract tracking numbers
3. **Automatic Registration**: Adds new shipments to user accounts
4. **Status Updates**: Fetches initial tracking information

### Supported Tracking Formats
- UPS: 1Z followed by 16 alphanumeric characters
- FedEx: 12 or 20 digit numbers
- USPS: 22-digit numbers starting with 9
- DHL: 2 letters + 9 digits + 2 letters

## Ship24 API Integration

The application integrates with Ship24 for comprehensive tracking:

```python
# Track a shipment
tracking_info = ship24.track_shipment(tracking_number)

# Get detailed tracking information
details = ship24.get_tracking_info(tracking_number)
```

## OpenAI Integration

The AI assistant provides natural language responses:

```python
# Generate response with context
response = ai_assistant.generate_response(
    user_message="Where is my package?",
    user_shipments=["Tracking: 123456789, Status: In Transit"],
    context="User: john_doe"
)
```

## Deployment on Render

1. Push your code to GitHub
2. Connect your repository to Render
3. Use the provided `render.yaml` configuration
4. Set environment variables in Render dashboard
5. Deploy the service

### Render Configuration

The `render.yaml` file includes:
- Web service configuration
- PostgreSQL database setup
- Environment variable definitions
- Auto-deploy settings

## Security Features

- **Password Hashing**: Werkzeug security for password hashing
- **JWT Tokens**: Secure authentication with expiration
- **CORS Protection**: Configured for specific origins
- **Input Validation**: Request data validation
- **Error Handling**: Comprehensive error responses

## Monitoring and Logging

- Health check endpoint for uptime monitoring
- Error logging for debugging
- Background email processing with error recovery
- Database connection monitoring

## Development

### Running in Development Mode
```bash
export FLASK_ENV=development
python app.py
```

### Testing the API
Use tools like Postman or curl to test endpoints:

```bash
# Register a user
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "email": "test@example.com", "password": "password123"}'

# Login
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'
```

## Troubleshooting

### Common Issues

1. **Database Connection**: Ensure PostgreSQL is running and credentials are correct
2. **API Keys**: Verify OpenAI and Ship24 API keys are valid
3. **Email Access**: Check email credentials and IMAP settings
4. **Port Conflicts**: Make sure port 5000 is available

### Debug Mode

Enable debug mode for detailed error messages:
```bash
export FLASK_ENV=development
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.