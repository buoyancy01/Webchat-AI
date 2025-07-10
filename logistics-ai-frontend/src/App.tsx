import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { WebSocketProvider } from './context/WebSocketContext';
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import { Toaster } from '@/components/ui/sonner';
import { useState } from 'react';

function AppRoutes() {
  const { isAuthenticated, loading } = useAuth();
  const [shipmentUpdateTrigger, setShipmentUpdateTrigger] = useState(0);

  const handleShipmentUpdate = (data: any) => {
    // Trigger a re-render or state update in Dashboard
    setShipmentUpdateTrigger(prev => prev + 1);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <Routes>
      <Route 
        path="/login" 
        element={!isAuthenticated ? <LoginPage /> : <Navigate to="/dashboard" />} 
      />
      <Route 
        path="/dashboard" 
        element={isAuthenticated ? <Dashboard key={shipmentUpdateTrigger} /> : <Navigate to="/login" />} 
      />
      <Route 
        path="/" 
        element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} />} 
      />
    </Routes>
  );
}

export default function App() {
  const [shipmentUpdateTrigger, setShipmentUpdateTrigger] = useState(0);

  const handleShipmentUpdate = (data: any) => {
    // This will cause Dashboard to re-render and fetch fresh data
    setShipmentUpdateTrigger(prev => prev + 1);
  };

  return (
    <Router>
      <AuthProvider>
        <WebSocketProvider onShipmentUpdate={handleShipmentUpdate}>
          <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900">
            <AppRoutes key={shipmentUpdateTrigger} />
            <Toaster />
          </div>
        </WebSocketProvider>
      </AuthProvider>
    </Router>
  );
}
