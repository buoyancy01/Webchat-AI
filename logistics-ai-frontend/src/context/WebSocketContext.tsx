import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuth } from './AuthContext';
import { toast } from 'sonner';

interface WebSocketContextType {
  socket: Socket | null;
  isConnected: boolean;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  lastUpdate: Date | null;
}

const WebSocketContext = createContext<WebSocketContextType>({
  socket: null,
  isConnected: false,
  connectionStatus: 'disconnected',
  lastUpdate: null
});

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

interface WebSocketProviderProps {
  children: React.ReactNode;
  onShipmentUpdate?: (data: any) => void;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ 
  children, 
  onShipmentUpdate 
}) => {
  const { token, isAuthenticated } = useAuth();
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';
  // Flask-SocketIO runs on the same port as the HTTP server, no need to convert to ws://

  const connect = () => {
    if (!isAuthenticated || !token) {
      console.log('Not authenticated, skipping WebSocket connection');
      setConnectionStatus('disconnected');
      return;
    }

    // Validate token format
    if (!token.startsWith('Bearer ') && !token.includes('.')) {
      console.error('Invalid token format for WebSocket connection');
      setConnectionStatus('error');
      return;
    }

    console.log('Connecting to WebSocket...', API_BASE_URL);
    console.log('Using token:', token.substring(0, 20) + '...');
    setConnectionStatus('connecting');

    const newSocket = io(API_BASE_URL, {
      auth: {
        token: token
      },
      transports: ['polling', 'websocket'], // Try polling first, then websocket
      timeout: 20000, // Increase timeout
      reconnection: true,
      reconnectionAttempts: maxReconnectAttempts,
      reconnectionDelay: 2000, // Increase initial delay
      reconnectionDelayMax: 10000, // Increase max delay
      forceNew: true, // Force a new connection
    });

    // Connection events
    newSocket.on('connect', () => {
      console.log('WebSocket connected successfully');
      setIsConnected(true);
      setConnectionStatus('connected');
      reconnectAttemptsRef.current = 0;
      
      // Join shipment updates room
      newSocket.emit('join_shipment_updates', { token });
    });

    newSocket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      setIsConnected(false);
      setConnectionStatus('disconnected');
      
      // Attempt reconnection if not a manual disconnect
      if (reason !== 'io client disconnect' && reconnectAttemptsRef.current < maxReconnectAttempts) {
        scheduleReconnect();
      }
    });

    newSocket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error.message || error);
      setIsConnected(false);
      setConnectionStatus('error');
      
      reconnectAttemptsRef.current++;
      console.log(`Connection attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts} failed`);
      
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        scheduleReconnect();
      } else {
        console.error('Max reconnection attempts reached');
        toast.error('Failed to connect to real-time updates. Please refresh the page.', {
          id: 'websocket-error', // Prevent duplicate toasts
          duration: 10000
        });
      }
    });

    // Application events
    newSocket.on('connection_status', (data) => {
      console.log('Connection status:', data);
      setLastUpdate(new Date());
    });

    newSocket.on('shipment_update', (data) => {
      console.log('Received shipment update:', data);
      setLastUpdate(new Date());
      
      // Show notification for status changes
      if (data.type === 'status_change') {
        toast.success(
          `Shipment ${data.shipment.tracking_number} status updated to ${data.shipment.status}`,
          {
            duration: 5000,
            action: {
              label: 'View',
              onClick: () => {
                // Could scroll to shipment or open details
                console.log('View shipment clicked');
              }
            }
          }
        );
      } else if (data.type === 'new_shipment') {
        toast.info(`New shipment added: ${data.shipment.tracking_number}`);
      }
      
      // Call the callback if provided
      if (onShipmentUpdate) {
        onShipmentUpdate(data);
      }
    });

    newSocket.on('joined_updates', (data) => {
      if (data.status === 'success') {
        console.log('Successfully joined shipment updates room');
      } else {
        console.error('Failed to join updates room:', data.message);
      }
    });

    setSocket(newSocket);
  };

  const scheduleReconnect = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    
    const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
    console.log(`Scheduling reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1})`);
    
    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
    }, delay);
  };

  const disconnect = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (socket) {
      console.log('Disconnecting WebSocket...');
      socket.disconnect();
      setSocket(null);
    }
    
    setIsConnected(false);
    setConnectionStatus('disconnected');
    reconnectAttemptsRef.current = 0;
  };

  // Connect when authenticated
  useEffect(() => {
    if (isAuthenticated && token) {
      connect();
    } else {
      disconnect();
    }
    
    return () => {
      disconnect();
    };
  }, [isAuthenticated, token]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  const value: WebSocketContextType = {
    socket,
    isConnected,
    connectionStatus,
    lastUpdate
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};