import React, { useState, useEffect } from 'react';
import { useWebSocket } from '../context/WebSocketContext';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';

export const WebSocketDebugger: React.FC = () => {
  const { socket, isConnected, connectionStatus, lastUpdate } = useWebSocket();
  const { token, isAuthenticated } = useAuth();
  const [logs, setLogs] = useState<string[]>([]);

  const addLog = (message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev.slice(-9), `[${timestamp}] ${message}`]);
  };

  useEffect(() => {
    if (socket) {
      const handleConnect = () => addLog('✅ WebSocket connected');
      const handleDisconnect = (reason: string) => addLog(`❌ WebSocket disconnected: ${reason}`);
      const handleConnectError = (error: any) => addLog(`🔥 Connection error: ${error.message || error}`);
      const handleConnectionStatus = (data: any) => addLog(`📡 Status: ${JSON.stringify(data)}`);

      socket.on('connect', handleConnect);
      socket.on('disconnect', handleDisconnect);
      socket.on('connect_error', handleConnectError);
      socket.on('connection_status', handleConnectionStatus);

      return () => {
        socket.off('connect', handleConnect);
        socket.off('disconnect', handleDisconnect);
        socket.off('connect_error', handleConnectError);
        socket.off('connection_status', handleConnectionStatus);
      };
    }
  }, [socket]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'bg-green-500';
      case 'connecting': return 'bg-yellow-500';
      case 'disconnected': return 'bg-gray-500';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  const testConnection = () => {
    if (socket && isConnected) {
      addLog('🧪 Testing connection...');
      socket.emit('join_shipment_updates', { token });
    } else {
      addLog('❌ Not connected - cannot test');
    }
  };

  const clearLogs = () => {
    setLogs([]);
  };

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          🔌 WebSocket Debug Panel
          <Badge className={getStatusColor(connectionStatus)}>
            {connectionStatus}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Connection Status */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <strong>Connected:</strong> {isConnected ? '✅ Yes' : '❌ No'}
          </div>
          <div>
            <strong>Authenticated:</strong> {isAuthenticated ? '✅ Yes' : '❌ No'}
          </div>
          <div>
            <strong>Socket ID:</strong> {socket?.id || 'N/A'}
          </div>
          <div>
            <strong>Last Update:</strong> {lastUpdate?.toLocaleTimeString() || 'Never'}
          </div>
          <div className="col-span-2">
            <strong>Token:</strong> {token ? `${token.substring(0, 20)}...` : 'None'}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <Button onClick={testConnection} disabled={!isConnected} size="sm">
            Test Connection
          </Button>
          <Button onClick={clearLogs} variant="outline" size="sm">
            Clear Logs
          </Button>
        </div>

        {/* Event Logs */}
        <div className="bg-gray-50 dark:bg-gray-800 p-3 rounded-lg">
          <h4 className="font-medium mb-2">Event Logs:</h4>
          <div className="space-y-1 text-xs font-mono max-h-40 overflow-y-auto">
            {logs.length === 0 ? (
              <div className="text-gray-500">No events logged yet...</div>
            ) : (
              logs.map((log, index) => (
                <div key={index} className="text-gray-700 dark:text-gray-300">
                  {log}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Troubleshooting */}
        {connectionStatus === 'error' && (
          <div className="bg-red-50 dark:bg-red-900/20 p-3 rounded-lg">
            <h4 className="font-medium text-red-800 dark:text-red-200 mb-2">
              🛠️ Troubleshooting Tips:
            </h4>
            <ul className="text-sm text-red-700 dark:text-red-300 space-y-1">
              <li>• Check that the backend server is running</li>
              <li>• Verify your authentication token is valid</li>
              <li>• Try refreshing the page</li>
              <li>• Check browser console for detailed errors</li>
              <li>• Ensure no firewall is blocking the connection</li>
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default WebSocketDebugger;