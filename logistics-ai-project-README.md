# LogisticsAI - Smart Shipment Tracking Platform

A complete AI-powered logistics platform featuring real-time shipment tracking, intelligent chat assistance, and automated email processing. Built with React frontend and Flask backend.

## 🚀 Features

### Frontend (React + TypeScript)
- **Modern UI**: Beautiful, responsive design with dark mode support
- **Authentication**: Secure login and registration system
- **Dashboard**: Comprehensive shipment management interface
- **AI Chat**: Real-time conversation with AI assistant
- **Real-time Updates**: Live tracking status updates
- **Mobile Responsive**: Optimized for all devices

### Backend (Flask + Python)
- **RESTful API**: Complete API for all operations
- **JWT Authentication**: Secure token-based authentication
- **OpenAI Integration**: GPT-powered chat assistant
- **Ship24 API**: Real-time shipment tracking
- **Email Automation**: Automatic tracking number extraction
- **Database**: PostgreSQL with SQLAlchemy ORM

## 🛠 Tech Stack

### Frontend
- **React 19** with TypeScript
- **Vite** for fast development
- **Tailwind CSS V4** for styling
- **ShadCN UI** components
- **React Router** for navigation
- **Sonner** for notifications

### Backend
- **Flask 2.3.3** web framework
- **SQLAlchemy** ORM
- **PostgreSQL** database
- **OpenAI GPT-3.5-turbo** for AI chat
- **Ship24 API** for tracking
- **JWT** for authentication
- **Flask-Mail** for email processing

## 📁 Project Structure

```
logistics-ai-project/
├── logistics-ai-frontend/          # React frontend
│   ├── src/
│   │   ├── components/            # UI components
│   │   ├── pages/                # Page components
│   │   ├── context/              # React context
│   │   ├── lib/                  # Utilities
│   │   └── hooks/                # Custom hooks
│   ├── public/                   # Static assets
│   └── package.json             # Dependencies
│
├── logistics-ai-backend/           # Flask backend
│   ├── app.py                    # Main Flask application
│   ├── requirements.txt          # Python dependencies
│   ├── render.yaml              # Render deployment config
│   ├── .env.example             # Environment variables template
│   └── README.md                # Backend documentation
│
└── README.md                     # This file
```

## 🚀 Quick Start

### Prerequisites

- **Node.js 18+** and **bun**
- **Python 3.8+**
- **PostgreSQL** database
- **OpenAI API Key**
- **Ship24 API Key**
- **Email account** with IMAP access

### Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd logistics-ai-frontend
   ```

2. **Install dependencies:**
   ```bash
   bun install
   ```

3. **Create environment file:**
   ```bash
   echo "VITE_API_BASE_URL=http://localhost:5000" > .env
   ```

4. **Start development server:**
   ```bash
   bun dev
   ```

   Frontend will be available at `http://localhost:5173`

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd logistics-ai-backend
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

5. **Edit `.env` with your API keys:**
   ```env
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=postgresql://user:password@localhost/logistics_db
   OPENAI_API_KEY=your-openai-api-key
   SHIP24_API_KEY=your-ship24-api-key
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   ```

6. **Initialize database:**
   ```bash
   python -c "from app import app, db; app.app_context().push(); db.create_all()"
   ```

7. **Start the server:**
   ```bash
   python app.py
   ```

   Backend will be available at `http://localhost:5000`

## 🌐 Deployment

### Frontend Deployment (Render/Vercel/Netlify)

1. **Build the frontend:**
   ```bash
   cd logistics-ai-frontend
   bun build
   ```

2. **Deploy the `dist` folder** to your preferred hosting service

3. **Set environment variable:**
   ```
   VITE_API_BASE_URL=https://your-backend-url.com
   ```

### Backend Deployment (Render)

1. **Push code to GitHub repository**

2. **Connect to Render:**
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Create new Web Service
   - Connect your GitHub repository
   - Select the backend folder

3. **Use the provided `render.yaml`** or configure manually:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
   - **Environment Variables:** Set all required API keys

4. **Create PostgreSQL database** in Render and link to your service

### Environment Variables for Production

#### Frontend
```env
VITE_API_BASE_URL=https://your-backend-api-url.com
```

#### Backend
```env
SECRET_KEY=your-production-secret-key
DATABASE_URL=postgresql://user:password@host:port/database
OPENAI_API_KEY=sk-your-openai-key
SHIP24_API_KEY=your-ship24-key
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
IMAP_SERVER=imap.gmail.com
FLASK_ENV=production
```

## 🔧 API Documentation

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/register` | Register new user |
| POST | `/api/login` | User login |

### Shipment Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/shipments` | Get user shipments |
| POST | `/api/shipments` | Add new shipment |
| GET | `/api/track/<tracking_number>` | Track specific shipment |

### AI Chat Endpoint

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Send message to AI |

### Example API Usage

```javascript
// Register user
const response = await fetch('/api/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'johndoe',
    email: 'john@example.com',
    password: 'password123',
    company_name: 'Acme Corp'
  })
});

// Login
const loginResponse = await fetch('/api/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'johndoe',
    password: 'password123'
  })
});

const { token } = await loginResponse.json();

// Get shipments
const shipmentsResponse = await fetch('/api/shipments', {
  headers: { 'Authorization': `Bearer ${token}` }
});
```

## 🤖 AI Features

### Chat Assistant Capabilities
- **Shipment Status Queries**: "Where is my package with tracking number 123456?"
- **General Logistics Help**: "How long does shipping usually take?"
- **Contextual Responses**: AI knows about user's current shipments
- **Natural Language**: Conversational interface

### Email Automation
- **Automatic Detection**: Monitors emails for tracking numbers
- **Pattern Recognition**: Supports UPS, FedEx, USPS, DHL formats
- **Auto-Registration**: Adds shipments to user accounts
- **Real-time Processing**: Continuous email monitoring

## 🔒 Security Features

- **JWT Authentication**: Secure token-based auth with expiration
- **Password Hashing**: Werkzeug security for password protection
- **CORS Protection**: Configured for production security
- **Input Validation**: Request data validation and sanitization
- **API Rate Limiting**: Protection against abuse

## 📊 Database Schema

### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    company_name VARCHAR(120),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Shipments Table
```sql
CREATE TABLE shipments (
    id SERIAL PRIMARY KEY,
    tracking_number VARCHAR(100) NOT NULL,
    carrier VARCHAR(50),
    description TEXT,
    origin VARCHAR(200),
    destination VARCHAR(200),
    status VARCHAR(50),
    estimated_delivery TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER REFERENCES users(id)
);
```

## 🧪 Testing

### Frontend Testing
```bash
cd logistics-ai-frontend
bun test
```

### Backend Testing
```bash
cd logistics-ai-backend
python -m pytest tests/
```

### API Testing with curl
```bash
# Health check
curl http://localhost:5000/api/health

# Register user
curl -X POST http://localhost:5000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "email": "test@example.com", "password": "password123"}'
```

## 🔧 Development

### Running in Development Mode

1. **Start backend:**
   ```bash
   cd logistics-ai-backend
   export FLASK_ENV=development
   python app.py
   ```

2. **Start frontend:**
   ```bash
   cd logistics-ai-frontend
   bun dev
   ```

### Code Quality Tools

- **Frontend**: ESLint, Prettier, TypeScript
- **Backend**: Black, Flake8, mypy
- **Git Hooks**: Pre-commit hooks for code quality

## 📈 Monitoring

### Health Endpoints
- **Backend**: `GET /api/health`
- **Database**: Connection monitoring
- **Email**: Processing status tracking

### Logging
- **Application Logs**: Structured logging with levels
- **Error Tracking**: Comprehensive error handling
- **Performance**: Request/response timing

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch:** `git checkout -b feature/amazing-feature`
3. **Commit changes:** `git commit -m 'Add amazing feature'`
4. **Push to branch:** `git push origin feature/amazing-feature`
5. **Open Pull Request**

### Development Guidelines
- Follow TypeScript/Python best practices
- Add tests for new features
- Update documentation
- Ensure responsive design

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Common Issues

1. **CORS Errors**: Check API URL configuration
2. **Database Connection**: Verify PostgreSQL credentials
3. **API Keys**: Ensure OpenAI and Ship24 keys are valid
4. **Email Monitoring**: Check IMAP settings and credentials

### Getting Help

- 📧 Email: support@logisticsai.com
- 💬 Discord: [Join our community](https://discord.gg/logisticsai)
- 📚 Documentation: [Full docs](https://docs.logisticsai.com)
- 🐛 Issues: [GitHub Issues](https://github.com/your-repo/issues)

## 🎯 Roadmap

- [ ] **Mobile App**: Native iOS/Android applications
- [ ] **Real-time Notifications**: Push notifications for status updates
- [ ] **Advanced Analytics**: Shipment analytics and reporting
- [ ] **Multi-language Support**: Internationalization
- [ ] **API Rate Limiting**: Enhanced security features
- [ ] **Webhook Support**: Real-time tracking updates

---

**Built with ❤️ for the logistics industry**