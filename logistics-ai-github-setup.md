# GitHub and Render Deployment Setup

This guide will help you set up the LogisticsAI project on GitHub and deploy it to Render.

## 🗂 GitHub Repository Setup

### 1. Create GitHub Repository

1. Go to [GitHub](https://github.com) and sign in
2. Click **"New repository"**
3. Repository name: `logistics-ai-platform`
4. Description: `AI-powered logistics platform with real-time shipment tracking and chat assistance`
5. Choose **Public** or **Private**
6. Initialize with README: **No** (we have our own)
7. Click **"Create repository"**

### 2. Upload Project Files

#### Option A: Using Git Command Line

```bash
# Navigate to your project directory
cd /path/to/your/project

# Initialize git repository
git init

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: LogisticsAI platform with React frontend and Flask backend"

# Add remote origin
git remote add origin https://github.com/yourusername/logistics-ai-platform.git

# Push to GitHub
git push -u origin main
```

#### Option B: Using GitHub Desktop

1. Download and install [GitHub Desktop](https://desktop.github.com/)
2. Sign in to your GitHub account
3. **File** → **Add Local Repository**
4. Select your project folder
5. Click **"Publish repository"**
6. Choose repository name and visibility
7. Click **"Publish Repository"**

### 3. Repository Structure

Your GitHub repository should look like this:

```
logistics-ai-platform/
├── logistics-ai-frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
├── logistics-ai-backend/
│   ├── app.py
│   ├── requirements.txt
│   ├── render.yaml
│   └── ...
├── README.md
├── logistics-ai-project-README.md
└── logistics-ai-github-setup.md
```

## 🌐 Render Deployment

### Backend Deployment

#### 1. Create Render Account
- Go to [Render](https://render.com)
- Sign up with GitHub account
- Verify your email

#### 2. Deploy Backend Service

1. **Create Web Service:**
   - Click **"New +"** → **"Web Service"**
   - Connect GitHub repository
   - Select `logistics-ai-platform`
   - Choose **"Backend"** folder or root if backend is in root

2. **Configure Service:**
   - **Name**: `logistics-ai-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: `Free`

3. **Environment Variables:**
   ```
   SECRET_KEY=your-super-secret-key-generate-new-one
   FLASK_ENV=production
   OPENAI_API_KEY=sk-your-openai-api-key-here
   SHIP24_API_KEY=your-ship24-api-key-here
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   IMAP_SERVER=imap.gmail.com
   ```

4. **Create Database:**
   - Click **"New +"** → **"PostgreSQL"**
   - **Name**: `logistics-db`
   - **Plan**: `Free`
   - **Region**: Same as your web service
   - After creation, copy the **External Database URL**

5. **Add Database URL:**
   - Go back to your web service
   - **Environment** → **Add Environment Variable**
   - **Key**: `DATABASE_URL`
   - **Value**: Paste the PostgreSQL connection string

6. **Deploy:**
   - Click **"Create Web Service"**
   - Wait for deployment (5-10 minutes)
   - Your backend will be available at: `https://logistics-ai-backend-xxx.onrender.com`

### Frontend Deployment

#### Option 1: Render Static Site

1. **Create Static Site:**
   - Click **"New +"** → **"Static Site"**
   - Connect same GitHub repository
   - **Root Directory**: `logistics-ai-frontend`

2. **Configure Build:**
   - **Build Command**: `bun install && bun build`
   - **Publish Directory**: `dist`

3. **Environment Variables:**
   ```
   VITE_API_BASE_URL=https://logistics-ai-backend-xxx.onrender.com
   ```

4. **Deploy:**
   - Click **"Create Static Site"**
   - Your frontend will be available at: `https://logistics-ai-frontend-xxx.onrender.com`

#### Option 2: Vercel (Recommended for Frontend)

1. Go to [Vercel](https://vercel.com)
2. Sign up with GitHub
3. **Import Project** → Select your repository
4. **Root Directory**: `logistics-ai-frontend`
5. **Framework Preset**: `Vite`
6. **Environment Variables:**
   ```
   VITE_API_BASE_URL=https://logistics-ai-backend-xxx.onrender.com
   ```
7. Click **"Deploy"**

## 🔐 API Keys Setup

### 1. OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com)
2. Sign up/Login
3. **API Keys** → **"Create new secret key"**
4. Copy the key (starts with `sk-`)
5. Add to Render environment variables

### 2. Ship24 API Key

1. Go to [Ship24](https://ship24.com)
2. Sign up for developer account
3. **Dashboard** → **API Keys**
4. Copy your API key
5. Add to Render environment variables

### 3. Email Configuration

#### Gmail Setup (Recommended)
1. Enable 2-Factor Authentication on Gmail
2. Generate App Password:
   - Google Account → Security → 2-Step Verification
   - App passwords → Select app: Mail
   - Generate password
3. Use this app password (not your regular password)

#### Environment Variables:
```
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-16-character-app-password
```

## 🧪 Testing Deployment

### 1. Test Backend Health
```bash
curl https://logistics-ai-backend-xxx.onrender.com/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00.000Z"
}
```

### 2. Test Registration
```bash
curl -X POST https://logistics-ai-backend-xxx.onrender.com/api/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "company_name": "Test Company"
  }'
```

### 3. Test Frontend
- Visit your frontend URL
- Try registration and login
- Add a test tracking number
- Test AI chat functionality

## 🔧 Troubleshooting

### Common Deployment Issues

#### Backend Issues

1. **Build Fails:**
   ```
   Error: Could not find a version that satisfies the requirement
   ```
   **Solution:** Check Python version in `runtime.txt`:
   ```
   python-3.11.0
   ```

2. **Database Connection Error:**
   ```
   Error: could not connect to server
   ```
   **Solution:** Verify DATABASE_URL environment variable

3. **OpenAI API Error:**
   ```
   Error: Incorrect API key provided
   ```
   **Solution:** Verify OPENAI_API_KEY is correct and has credits

#### Frontend Issues

1. **API Connection Error:**
   ```
   Network Error: Failed to fetch
   ```
   **Solution:** Check VITE_API_BASE_URL points to correct backend

2. **Build Fails:**
   ```
   Error: Cannot resolve module
   ```
   **Solution:** Ensure all dependencies in package.json

3. **CORS Error:**
   ```
   Access blocked by CORS policy
   ```
   **Solution:** Backend CORS is configured for all origins in production

### Debug Mode

#### Backend Debug
Add environment variable:
```
FLASK_ENV=development
```

#### Frontend Debug
Check browser console for errors
Use Network tab to inspect API calls

## 📊 Monitoring

### Render Monitoring
- **Logs**: Render Dashboard → Your Service → Logs
- **Metrics**: CPU, Memory usage in dashboard
- **Health Checks**: Automatic health monitoring

### Custom Monitoring
```python
# Add to app.py for custom health checks
@app.route('/api/status')
def status():
    return jsonify({
        'database': 'connected' if db else 'disconnected',
        'openai': 'configured' if OPENAI_API_KEY else 'missing',
        'ship24': 'configured' if SHIP24_API_KEY else 'missing'
    })
```

## 🚀 Production Checklist

### Before Going Live

- [ ] Change SECRET_KEY to a strong, unique value
- [ ] Set FLASK_ENV=production
- [ ] Verify all API keys are working
- [ ] Test email automation
- [ ] Test all API endpoints
- [ ] Check frontend connects to backend
- [ ] Test user registration and login
- [ ] Test shipment tracking
- [ ] Test AI chat functionality
- [ ] Set up domain name (optional)
- [ ] Configure SSL certificates (automatic on Render/Vercel)

### Security Considerations

- [ ] Use environment variables for all secrets
- [ ] Enable CORS only for your domain in production
- [ ] Set strong passwords for database
- [ ] Monitor API usage and costs
- [ ] Set up error tracking (e.g., Sentry)
- [ ] Configure backup strategy for database

## 📞 Support

If you encounter issues:

1. **Check Logs**: Render Dashboard → Service → Logs
2. **Environment Variables**: Ensure all required vars are set
3. **API Keys**: Verify keys are valid and have proper permissions
4. **Network**: Check if services can communicate
5. **Documentation**: Re-read setup instructions

### Common Commands

```bash
# View Render logs
curl -H "Authorization: Bearer RENDER_API_KEY" \
  https://api.render.com/v1/services/SERVICE_ID/logs

# Test local backend
cd logistics-ai-backend
python app.py

# Test local frontend
cd logistics-ai-frontend
bun dev
```

---

**Deployment Complete! 🎉**

Your LogisticsAI platform should now be live and ready for use.