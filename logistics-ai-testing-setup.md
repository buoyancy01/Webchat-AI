# Testing Setup and Configuration

This document covers testing strategies, API testing, and quality assurance for the LogisticsAI platform.

## 🧪 Testing Strategy

### Frontend Testing (React + TypeScript)

#### Unit Tests
- Component testing with React Testing Library
- Hook testing with custom hook utilities
- Utility function testing with Jest

#### Integration Tests
- API integration testing
- Authentication flow testing
- User journey testing

#### E2E Tests
- End-to-end testing with Playwright
- Cross-browser compatibility
- Mobile responsiveness testing

### Backend Testing (Flask + Python)

#### Unit Tests
- API endpoint testing
- Database model testing
- Utility function testing

#### Integration Tests
- Database integration testing
- External API integration (OpenAI, Ship24)
- Email processing testing

#### Load Tests
- API performance testing
- Database stress testing
- Concurrent user testing

## 🛠 Test Setup

### Frontend Test Configuration

1. **Install testing dependencies:**
   ```bash
   cd logistics-ai-frontend
   bun add -D @testing-library/react @testing-library/jest-dom @testing-library/user-event
   bun add -D vitest @vitest/ui jsdom
   bun add -D playwright @playwright/test
   ```

2. **Create test configuration:**
   ```typescript
   // vitest.config.ts
   import { defineConfig } from 'vitest/config'
   import react from '@vitejs/plugin-react'
   import path from 'path'

   export default defineConfig({
     plugins: [react()],
     test: {
       globals: true,
       environment: 'jsdom',
       setupFiles: ['./src/test/setup.ts']
     },
     resolve: {
       alias: {
         '@': path.resolve(__dirname, './src')
       }
     }
   })
   ```

3. **Test setup file:**
   ```typescript
   // src/test/setup.ts
   import '@testing-library/jest-dom'
   import { beforeAll, afterEach, afterAll } from 'vitest'
   import { server } from './mocks/server'

   beforeAll(() => server.listen())
   afterEach(() => server.resetHandlers())
   afterAll(() => server.close())
   ```

### Backend Test Configuration

1. **Install testing dependencies:**
   ```bash
   cd logistics-ai-backend
   pip install pytest pytest-flask pytest-cov requests-mock
   ```

2. **Create test configuration:**
   ```python
   # conftest.py
   import pytest
   from app import app, db
   import tempfile
   import os

   @pytest.fixture
   def client():
       db_fd, app.config['DATABASE'] = tempfile.mkstemp()
       app.config['TESTING'] = True
       app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
       
       with app.test_client() as client:
           with app.app_context():
               db.create_all()
           yield client
           
       os.close(db_fd)
       os.unlink(app.config['DATABASE'])
   ```

## 📋 Test Examples

### Frontend Component Testing

```typescript
// src/test/components/LoginPage.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import LoginPage from '@/pages/LoginPage'
import { AuthProvider } from '@/context/AuthContext'

const renderLoginPage = () => {
  return render(
    <BrowserRouter>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </BrowserRouter>
  )
}

describe('LoginPage', () => {
  it('renders login form', () => {
    renderLoginPage()
    expect(screen.getByText('Welcome Back')).toBeInTheDocument()
    expect(screen.getByLabelText('Username')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
  })

  it('handles form submission', async () => {
    renderLoginPage()
    
    fireEvent.change(screen.getByLabelText('Username'), {
      target: { value: 'testuser' }
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'password123' }
    })
    
    fireEvent.click(screen.getByText('Sign In'))
    
    await waitFor(() => {
      expect(screen.getByText('Signing in...')).toBeInTheDocument()
    })
  })
})
```

### Backend API Testing

```python
# tests/test_auth.py
import json
import pytest
from app import app, db

def test_register_user(client):
    """Test user registration"""
    response = client.post('/api/register', 
        data=json.dumps({
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'password123',
            'company_name': 'Test Company'
        }),
        content_type='application/json'
    )
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['message'] == 'User created successfully'

def test_login_user(client):
    """Test user login"""
    # First register a user
    client.post('/api/register', 
        data=json.dumps({
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'password123'
        }),
        content_type='application/json'
    )
    
    # Then login
    response = client.post('/api/login',
        data=json.dumps({
            'username': 'testuser',
            'password': 'password123'
        }),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'token' in data
    assert 'user' in data

def test_protected_endpoint(client):
    """Test protected endpoint access"""
    response = client.get('/api/shipments')
    assert response.status_code == 401
    
    data = json.loads(response.data)
    assert data['message'] == 'Token is missing'
```

### API Integration Testing

```python
# tests/test_shipments.py
import json
import pytest
from unittest.mock import patch
from app import app, db

@pytest.fixture
def auth_headers(client):
    """Create authenticated user and return headers"""
    # Register user
    client.post('/api/register', 
        data=json.dumps({
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'password123'
        }),
        content_type='application/json'
    )
    
    # Login user
    response = client.post('/api/login',
        data=json.dumps({
            'username': 'testuser',
            'password': 'password123'
        }),
        content_type='application/json'
    )
    
    token = json.loads(response.data)['token']
    return {'Authorization': f'Bearer {token}'}

@patch('app.ship24.get_tracking_info')
def test_add_shipment(mock_ship24, client, auth_headers):
    """Test adding a new shipment"""
    mock_ship24.return_value = {
        'carrier': 'UPS',
        'status': 'In Transit'
    }
    
    response = client.post('/api/shipments',
        data=json.dumps({
            'tracking_number': '1Z999AA1234567890',
            'description': 'Test package'
        }),
        content_type='application/json',
        headers=auth_headers
    )
    
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data['message'] == 'Shipment added successfully'

def test_get_shipments(client, auth_headers):
    """Test retrieving user shipments"""
    response = client.get('/api/shipments', headers=auth_headers)
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'shipments' in data
    assert isinstance(data['shipments'], list)
```

## 🎭 Playwright E2E Tests

```typescript
// tests/e2e/user-journey.spec.ts
import { test, expect } from '@playwright/test'

test.describe('User Journey', () => {
  test('complete user flow', async ({ page }) => {
    // Go to application
    await page.goto('http://localhost:5173')
    
    // Should redirect to login page
    await expect(page).toHaveURL('/login')
    
    // Register new user
    await page.click('text=Register')
    await page.fill('[data-testid=username]', 'testuser')
    await page.fill('[data-testid=email]', 'test@example.com')
    await page.fill('[data-testid=password]', 'password123')
    await page.click('text=Create Account')
    
    // Login with new user
    await page.click('text=Login')
    await page.fill('[data-testid=username]', 'testuser')
    await page.fill('[data-testid=password]', 'password123')
    await page.click('text=Sign In')
    
    // Should be on dashboard
    await expect(page).toHaveURL('/dashboard')
    await expect(page.locator('text=Your Shipments')).toBeVisible()
    
    // Add a shipment
    await page.fill('[data-testid=tracking-input]', '1Z999AA1234567890')
    await page.click('text=Add')
    
    // Verify shipment appears
    await expect(page.locator('text=1Z999AA1234567890')).toBeVisible()
    
    // Test AI chat
    await page.fill('[data-testid=chat-input]', 'What is the status of my package?')
    await page.click('[data-testid=send-button]')
    
    // Verify AI response
    await expect(page.locator('[data-testid=chat-messages]')).toContainText('tracking')
  })
})
```

## 🚀 Running Tests

### Frontend Tests

```bash
cd logistics-ai-frontend

# Unit tests
bun test

# Unit tests with coverage
bun test --coverage

# Watch mode
bun test --watch

# E2E tests
bun playwright test

# E2E tests with UI
bun playwright test --ui
```

### Backend Tests

```bash
cd logistics-ai-backend

# All tests
pytest

# With coverage
pytest --cov=app

# Specific test file
pytest tests/test_auth.py

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

## 📊 Test Coverage

### Coverage Requirements
- **Frontend**: Minimum 80% code coverage
- **Backend**: Minimum 85% code coverage
- **Critical paths**: 100% coverage (auth, payments, data integrity)

### Coverage Reports

```bash
# Frontend coverage
bun test --coverage --reporter=html
open coverage/index.html

# Backend coverage
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

## 🔧 Mock Services

### API Mocking (Frontend)

```typescript
// src/test/mocks/handlers.ts
import { rest } from 'msw'

export const handlers = [
  rest.post('/api/login', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        token: 'mock-jwt-token',
        user: {
          id: 1,
          username: 'testuser',
          email: 'test@example.com'
        }
      })
    )
  }),
  
  rest.get('/api/shipments', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        shipments: [
          {
            id: 1,
            tracking_number: '1Z999AA1234567890',
            status: 'In Transit',
            carrier: 'UPS'
          }
        ]
      })
    )
  })
]
```

### External API Mocking (Backend)

```python
# tests/conftest.py
import pytest
from unittest.mock import patch

@pytest.fixture
def mock_openai():
    with patch('app.openai.OpenAI') as mock:
        mock_instance = mock.return_value
        mock_instance.chat.completions.create.return_value.choices[0].message.content = "Mock AI response"
        yield mock_instance

@pytest.fixture
def mock_ship24():
    with patch('app.ship24.get_tracking_info') as mock:
        mock.return_value = {
            'carrier': 'UPS',
            'status': 'In Transit',
            'estimated_delivery': '2024-01-15'
        }
        yield mock
```

## 📋 Test Checklist

### Before Deployment

#### Functionality Tests
- [ ] User registration and login
- [ ] Password hashing and validation
- [ ] JWT token generation and validation
- [ ] Shipment creation and retrieval
- [ ] AI chat functionality
- [ ] Email automation (if configured)
- [ ] Tracking number validation
- [ ] Database operations
- [ ] Error handling

#### Security Tests
- [ ] SQL injection protection
- [ ] XSS protection
- [ ] CSRF protection
- [ ] Authentication bypass attempts
- [ ] Authorization checks
- [ ] Input validation
- [ ] Rate limiting (if implemented)

#### Performance Tests
- [ ] API response times < 2s
- [ ] Database query optimization
- [ ] Frontend bundle size < 1MB
- [ ] Image optimization
- [ ] Caching strategies

#### Browser Compatibility
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Mobile browsers

#### Accessibility Tests
- [ ] Keyboard navigation
- [ ] Screen reader compatibility
- [ ] Color contrast ratios
- [ ] Focus management
- [ ] ARIA labels

## 🐛 Bug Tracking

### Issue Template

```markdown
**Bug Description:**
Clear description of the bug

**Steps to Reproduce:**
1. Go to...
2. Click on...
3. See error

**Expected Behavior:**
What should happen

**Actual Behavior:**
What actually happens

**Environment:**
- Browser: Chrome 120
- OS: macOS
- Version: 1.0.0

**Screenshots:**
If applicable

**Console Logs:**
Any error messages
```

### Test Data Management

```python
# tests/fixtures.py
import pytest
from app import db
from app.models import User, Shipment

@pytest.fixture
def sample_user():
    user = User(
        username='testuser',
        email='test@example.com',
        password_hash='hashed_password'
    )
    db.session.add(user)
    db.session.commit()
    return user

@pytest.fixture
def sample_shipments(sample_user):
    shipments = [
        Shipment(
            tracking_number='1Z999AA1234567890',
            carrier='UPS',
            status='In Transit',
            user_id=sample_user.id
        ),
        Shipment(
            tracking_number='123456789012',
            carrier='FedEx',
            status='Delivered',
            user_id=sample_user.id
        )
    ]
    for shipment in shipments:
        db.session.add(shipment)
    db.session.commit()
    return shipments
```

## 📈 Continuous Integration

### GitHub Actions (Optional)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: oven-sh/setup-bun@v1
      - run: cd logistics-ai-frontend && bun install
      - run: cd logistics-ai-frontend && bun test
      - run: cd logistics-ai-frontend && bun build

  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: cd logistics-ai-backend && pip install -r requirements.txt
      - run: cd logistics-ai-backend && pytest
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost/test
```

---

**Testing ensures quality and reliability! 🧪✅**