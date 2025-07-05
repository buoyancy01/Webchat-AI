// API utility functions for the logistics application
// This file provides helper functions for making API calls to the Flask backend

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

// Helper function to get auth headers
const getAuthHeaders = (token?: string): HeadersInit => {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  return headers;
};

// Helper function to handle API responses
const handleApiResponse = async (response: Response) => {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Network error' }));
    throw new Error(error.message || 'API request failed');
  }
  return response.json();
};

// API functions
export const api = {
  // Authentication
  login: async (username: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/api/login`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ username, password }),
    });
    return handleApiResponse(response);
  },

  register: async (username: string, email: string, password: string, companyName?: string) => {
    const response = await fetch(`${API_BASE_URL}/api/register`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ 
        username, 
        email, 
        password, 
        company_name: companyName 
      }),
    });
    return handleApiResponse(response);
  },

  // Shipments
  getShipments: async (token: string) => {
    const response = await fetch(`${API_BASE_URL}/api/shipments`, {
      headers: getAuthHeaders(token),
    });
    return handleApiResponse(response);
  },

  addShipment: async (token: string, trackingNumber: string) => {
    const response = await fetch(`${API_BASE_URL}/api/shipments`, {
      method: 'POST',
      headers: getAuthHeaders(token),
      body: JSON.stringify({ tracking_number: trackingNumber }),
    });
    return handleApiResponse(response);
  },

  trackShipment: async (token: string, trackingNumber: string) => {
    const response = await fetch(`${API_BASE_URL}/api/track/${trackingNumber}`, {
      headers: getAuthHeaders(token),
    });
    return handleApiResponse(response);
  },

  // Chat
  sendChatMessage: async (token: string, message: string) => {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: getAuthHeaders(token),
      body: JSON.stringify({ message }),
    });
    return handleApiResponse(response);
  },
};

export default api;