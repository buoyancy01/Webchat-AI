import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useWebSocket } from '@/context/WebSocketContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Package, 
  MessageCircle, 
  Plus, 
  Send, 
  LogOut, 
  User, 
  Search,
  Truck,
  Calendar,
  MapPin,
  Clock,
  Wifi,
  WifiOff,
  CheckCircle,
  Circle,
  ArrowRight,
  Plane,
  Warehouse,
  Home,
  AlertTriangle,
  RefreshCw
} from 'lucide-react';
import { toast } from 'sonner';

interface Shipment {
  id: number;
  tracking_number: string;
  carrier?: string;
  description?: string;
  origin?: string;
  destination?: string;
  status?: string;
  estimated_delivery?: string;
  created_at: string;
  updated_at: string;
}

interface ShipmentStage {
  id: string;
  name: string;
  description: string;
  icon: React.ReactNode;
  completed: boolean;
  current: boolean;
  timestamp?: string;
}

interface ChatMessage {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

export default function Dashboard() {
  const { user, logout, token } = useAuth();
  const { isConnected, connectionStatus, lastUpdate } = useWebSocket();
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      text: 'Hello! I\'m your AI logistics assistant. How can I help you track your shipments today?',
      sender: 'ai',
      timestamp: new Date()
    }
  ]);
  const [newMessage, setNewMessage] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [newTrackingNumber, setNewTrackingNumber] = useState('');
  const [addingShipment, setAddingShipment] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [searchTerm, setSearchTerm] = useState('');
  
  // Live tracking states
  const [liveTrackingEnabled, setLiveTrackingEnabled] = useState(true);
  const [updatingShipments, setUpdatingShipments] = useState<Set<number>>(new Set());
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Handle real-time shipment updates
  const handleShipmentUpdate = (data: any) => {
    console.log('Handling real-time shipment update:', data);
    
    if (data.type === 'new_shipment' || data.type === 'status_change') {
      // Refresh shipments to get the latest data
      fetchShipments();
    }
  };
  
  useEffect(() => {
    fetchShipments();
    
    // Start live tracking
    if (liveTrackingEnabled) {
      startLiveTracking();
    }
    
    // Cleanup on unmount
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [liveTrackingEnabled]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatEndRef.current) {
      setTimeout(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    }
  }, [chatMessages]);

  const fetchShipments = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/shipments`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setShipments(data.shipments || []);
      } else {
        toast.error('Failed to fetch shipments');
      }
    } catch (error) {
      toast.error('Error fetching shipments');
    } finally {
      setLoading(false);
    }
  };

  const startLiveTracking = () => {
    // Clear existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    
    // Set up polling every 2 minutes for active shipments
    intervalRef.current = setInterval(async () => {
      await updateActiveShipments();
    }, 120000); // 2 minutes
    
    console.log('Live tracking started - polling every 2 minutes');
  };
  
  const updateActiveShipments = async () => {
    const activeShipments = shipments.filter(shipment => 
      !['delivered', 'cancelled', 'returned'].includes(shipment.status?.toLowerCase() || '')
    );
    
    if (activeShipments.length === 0) {
      console.log('No active shipments to update');
      return;
    }
    
    console.log(`Updating ${activeShipments.length} active shipments`);
    
    const updatePromises = activeShipments.map(async (shipment) => {
      try {
        setUpdatingShipments(prev => new Set(prev).add(shipment.id));
        
        const response = await fetch(`${API_BASE_URL}/api/track/${shipment.tracking_number}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.updated && data.shipment) {
            // Check if status actually changed
            const oldStatus = shipment.status;
            const newStatus = data.shipment.status;
            
            if (oldStatus !== newStatus) {
              toast.success(`${shipment.tracking_number}: Status updated to ${newStatus}`, {
                duration: 5000,
              });
            }
          }
        }
      } catch (error) {
        console.error(`Failed to update shipment ${shipment.tracking_number}:`, error);
      } finally {
        setUpdatingShipments(prev => {
          const newSet = new Set(prev);
          newSet.delete(shipment.id);
          return newSet;
        });
      }
    });
    
    await Promise.all(updatePromises);
    
    // Refresh the shipments list
    await fetchShipments();
  };
  
  const toggleLiveTracking = () => {
    const newStatus = !liveTrackingEnabled;
    setLiveTrackingEnabled(newStatus);
    
    if (newStatus) {
      startLiveTracking();
      toast.success('Live tracking enabled');
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      toast.info('Live tracking disabled');
    }
  };

  const addShipment = async () => {
    if (!newTrackingNumber.trim()) {
      toast.error('Please enter a tracking number');
      return;
    }

    setAddingShipment(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/shipments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ tracking_number: newTrackingNumber }),
      });

      if (response.ok) {
        toast.success('Shipment added successfully');
        setNewTrackingNumber('');
        fetchShipments();
      } else {
        const data = await response.json();
        toast.error(data.message || 'Failed to add shipment');
      }
    } catch (error) {
      toast.error('Error adding shipment');
    } finally {
      setAddingShipment(false);
    }
  };

  const trackShipment = async (trackingNumber: string) => {
    const shipment = shipments.find(s => s.tracking_number === trackingNumber);
    if (!shipment) return;
    
    setUpdatingShipments(prev => new Set(prev).add(shipment.id));
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/track/${trackingNumber}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        if (data.updated) {
          toast.success('Tracking information updated');
        } else {
          toast.info('Tracking information is up to date');
        }
        fetchShipments();
      } else {
        toast.error('Failed to track shipment');
      }
    } catch (error) {
      toast.error('Error tracking shipment');
    } finally {
      setUpdatingShipments(prev => {
        const newSet = new Set(prev);
        newSet.delete(shipment.id);
        return newSet;
      });
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim() || chatLoading) return;

    const messageText = newMessage.trim();
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: messageText,
      sender: 'user',
      timestamp: new Date()
    };

    setChatMessages(prev => [...prev, userMessage]);
    setNewMessage('');
    setChatLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message: messageText }),
      });

      if (response.ok) {
        const data = await response.json();
        const aiMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          text: data.response,
          sender: 'ai',
          timestamp: new Date()
        };
        setChatMessages(prev => [...prev, aiMessage]);
      } else {
        const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
        toast.error(errorData.message || 'Failed to send message');
        // Add error message to chat
        const errorMessage: ChatMessage = {
          id: (Date.now() + 2).toString(),
          text: 'Sorry, I\'m having trouble responding right now. Please try again.',
          sender: 'ai',
          timestamp: new Date()
        };
        setChatMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error('Chat error:', error);
      toast.error('Network error - please check your connection');
      // Add error message to chat
      const errorMessage: ChatMessage = {
        id: (Date.now() + 3).toString(),
        text: 'I\'m having connection issues. Please try again.',
        sender: 'ai',
        timestamp: new Date()
      };
      setChatMessages(prev => [...prev, errorMessage]);
    } finally {
      setChatLoading(false);
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status?.toLowerCase()) {
      case 'delivered': return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'in transit': 
      case 'in_transit': return <Truck className="h-4 w-4 text-blue-600" />;
      case 'out for delivery': 
      case 'out_for_delivery': return <ArrowRight className="h-4 w-4 text-purple-600" />;
      case 'processing': return <RefreshCw className="h-4 w-4 text-yellow-600 animate-spin" />;
      case 'pending': return <Clock className="h-4 w-4 text-yellow-600" />;
      case 'delayed': 
      case 'exception': return <AlertTriangle className="h-4 w-4 text-red-600" />;
      case 'shipped': return <Plane className="h-4 w-4 text-indigo-600" />;
      default: return <Package className="h-4 w-4 text-gray-600" />;
    }
  };
  
  const getCarrierIcon = (carrier?: string) => {
    if (!carrier) return <Truck className="h-5 w-5 text-blue-600" />;
    
    const carrierLower = carrier.toLowerCase();
    if (carrierLower.includes('fedex')) return <Plane className="h-5 w-5 text-purple-600" />;
    if (carrierLower.includes('ups')) return <Truck className="h-5 w-5 text-amber-600" />;
    if (carrierLower.includes('dhl')) return <Plane className="h-5 w-5 text-red-600" />;
    if (carrierLower.includes('usps')) return <Truck className="h-5 w-5 text-blue-800" />;
    return <Truck className="h-5 w-5 text-blue-600" />;
  };
  
  const renderEnhancedProgressBar = (shipment: Shipment) => {
    const progress = getStatusProgress(shipment.status);
    
    return (
      <div className="mb-4">
        <div className="flex justify-between text-xs text-gray-500 mb-2">
          <span className="flex items-center space-x-1">
            {getStatusIcon(shipment.status)}
            <span>Progress</span>
          </span>
          <span className="font-medium">{progress}%</span>
        </div>
        
        {/* Enhanced Progress Bar with Stage Markers */}
        <div className="relative">
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div 
              className={`h-3 rounded-full transition-all duration-500 ${
                shipment.status?.toLowerCase() === 'delivered' ? 'bg-gradient-to-r from-green-400 to-green-600' :
                shipment.status?.toLowerCase().includes('delayed') || shipment.status?.toLowerCase() === 'exception' ? 'bg-gradient-to-r from-red-400 to-red-600' :
                'bg-gradient-to-r from-blue-400 to-blue-600'
              }`}
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          
          {/* Stage Markers */}
          <div className="absolute top-0 w-full flex justify-between px-1" style={{ marginTop: '-2px' }}>
            {[20, 40, 60, 80].map((position, index) => {
              const isPassed = progress > position;
              return (
                <div
                  key={position}
                  className={`w-2 h-2 rounded-full border-2 transition-all duration-300 ${
                    isPassed 
                      ? 'bg-white border-blue-600 shadow-sm' 
                      : 'bg-gray-300 border-gray-400'
                  }`}
                />
              );
            })}
          </div>
        </div>
        
        {/* Status Text with Animation */}
        <div className="mt-2 text-center">
          <span className={`text-xs font-medium ${
            shipment.status?.toLowerCase() === 'delivered' ? 'text-green-700' :
            shipment.status?.toLowerCase().includes('delayed') || shipment.status?.toLowerCase() === 'exception' ? 'text-red-700' :
            'text-blue-700'
          }`}>
            {shipment.status?.toLowerCase() === 'processing' ? (
              <span className="flex items-center justify-center space-x-1">
                <RefreshCw className="h-3 w-3 animate-spin" />
                <span>Processing...</span>
              </span>
            ) : (
              shipment.status || 'Unknown'
            )}
          </span>
        </div>
      </div>
    );
  };

  const getShipmentStages = (shipment: Shipment): ShipmentStage[] => {
    const currentStatus = shipment.status?.toLowerCase() || 'unknown';
    
    const stages: ShipmentStage[] = [
      {
        id: 'created',
        name: 'Order Created',
        description: 'Shipment has been created',
        icon: <Package className="h-4 w-4" />,
        completed: true,
        current: currentStatus === 'pending' || currentStatus === 'created',
        timestamp: shipment.created_at
      },
      {
        id: 'processing',
        name: 'Processing',
        description: 'Package is being prepared',
        icon: <Warehouse className="h-4 w-4" />,
        completed: !['pending', 'created'].includes(currentStatus),
        current: currentStatus === 'processing',
      },
      {
        id: 'shipped',
        name: 'Shipped',
        description: 'Package has left the origin facility',
        icon: <Plane className="h-4 w-4" />,
        completed: ['in_transit', 'in transit', 'out_for_delivery', 'out for delivery', 'delivered'].includes(currentStatus),
        current: currentStatus === 'shipped',
      },
      {
        id: 'in_transit',
        name: 'In Transit',
        description: 'Package is on its way',
        icon: <Truck className="h-4 w-4" />,
        completed: ['out_for_delivery', 'out for delivery', 'delivered'].includes(currentStatus),
        current: ['in_transit', 'in transit'].includes(currentStatus),
      },
      {
        id: 'out_for_delivery',
        name: 'Out for Delivery',
        description: 'Package is being delivered today',
        icon: <ArrowRight className="h-4 w-4" />,
        completed: currentStatus === 'delivered',
        current: ['out_for_delivery', 'out for delivery'].includes(currentStatus),
      },
      {
        id: 'delivered',
        name: 'Delivered',
        description: 'Package has been delivered',
        icon: <Home className="h-4 w-4" />,
        completed: currentStatus === 'delivered',
        current: currentStatus === 'delivered',
      }
    ];
    
    // Handle exception/delayed status
    if (currentStatus === 'delayed' || currentStatus === 'exception') {
      stages.forEach(stage => {
        if (stage.current) {
          stage.current = false;
        }
      });
      
      // Add or modify a stage to show the issue
      const issueStageIndex = stages.findIndex(s => s.id === 'in_transit');
      if (issueStageIndex !== -1) {
        stages[issueStageIndex] = {
          ...stages[issueStageIndex],
          name: currentStatus === 'delayed' ? 'Delayed' : 'Exception',
          description: currentStatus === 'delayed' ? 'Delivery has been delayed' : 'An exception occurred',
          icon: <AlertTriangle className="h-4 w-4" />,
          current: true
        };
      }
    }
    
    return stages;
  };
  
  const getStatusColor = (status?: string) => {
    switch (status?.toLowerCase()) {
      case 'delivered': return 'bg-green-100 text-green-800 border-green-200';
      case 'in transit': 
      case 'in_transit': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'out for delivery': 
      case 'out_for_delivery': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'processing': 
      case 'pending': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'delayed': 
      case 'exception': return 'bg-red-100 text-red-800 border-red-200';
      case 'shipped': return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusProgress = (status?: string) => {
    switch (status?.toLowerCase()) {
      case 'pending':
      case 'processing': return 25;
      case 'shipped':
      case 'in transit':
      case 'in_transit': return 50;
      case 'out for delivery':
      case 'out_for_delivery': return 75;
      case 'delivered': return 100;
      case 'delayed':
      case 'exception': return 40;
      default: return 10;
    }
  };
  
  const renderShipmentTimeline = (shipment: Shipment) => {
    const stages = getShipmentStages(shipment);
    
    return (
      <div className="mt-4">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Shipment Timeline</h4>
        <div className="space-y-3">
          {stages.map((stage, index) => (
            <div key={stage.id} className="flex items-center space-x-3 relative">
              {/* Stage Icon */}
              <div className={`flex-shrink-0 w-8 h-8 rounded-full border-2 flex items-center justify-center ${
                stage.completed ? 'bg-green-100 border-green-500 text-green-700' :
                stage.current ? 'bg-blue-100 border-blue-500 text-blue-700' :
                'bg-gray-100 border-gray-300 text-gray-400'
              }`}>
                {stage.completed ? <CheckCircle className="h-4 w-4" /> : stage.icon}
              </div>
              
              {/* Stage Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between">
                  <p className={`text-sm font-medium ${
                    stage.completed ? 'text-green-700' :
                    stage.current ? 'text-blue-700' :
                    'text-gray-500'
                  }`}>
                    {stage.name}
                  </p>
                  {stage.timestamp && (
                    <p className="text-xs text-gray-500">
                      {new Date(stage.timestamp).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </p>
                  )}
                </div>
                <p className={`text-xs ${
                  stage.completed ? 'text-green-600' :
                  stage.current ? 'text-blue-600' :
                  'text-gray-400'
                }`}>
                  {stage.description}
                </p>
              </div>
              
              {/* Connection Line */}
              {index < stages.length - 1 && (
                <div className={`absolute left-4 mt-8 w-0.5 h-6 ${
                  stages[index + 1].completed || stages[index + 1].current ? 'bg-blue-300' : 'bg-gray-200'
                }`} style={{ marginTop: '2rem' }} />
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const filteredShipments = shipments.filter(shipment => 
    shipment.tracking_number.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (shipment.carrier && shipment.carrier.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (shipment.status && shipment.status.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="bg-white dark:bg-gray-800 shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center space-x-3">
              <Truck className="h-8 w-8 text-blue-600" />
              <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                LogisticsAI
              </h1>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <User className="h-5 w-5 text-gray-500" />
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {user?.username}
                </span>
              </div>
              
              {/* Live Tracking Status */}
              <div className="flex items-center space-x-2">
                <div className={`flex items-center space-x-1 text-xs px-2 py-1 rounded-full ${
                  isConnected && connectionStatus === 'connected' ? 'bg-green-100 text-green-700' :
                  connectionStatus === 'connecting' ? 'bg-blue-100 text-blue-700' :
                  'bg-red-100 text-red-700'
                }`}>
                  {isConnected && connectionStatus === 'connected' ? (
                    <><Wifi className="h-3 w-3" /><span>Live</span></>
                  ) : connectionStatus === 'connecting' ? (
                    <><div className="animate-spin h-3 w-3 border border-blue-600 rounded-full border-t-transparent"></div><span>Connecting</span></>
                  ) : (
                    <><WifiOff className="h-3 w-3" /><span>Offline</span></>
                  )}
                </div>
                
                {lastUpdate && (
                  <span className="text-xs text-gray-500">
                    Last update: {lastUpdate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
              </div>
              
              <Button variant="outline" size="sm" onClick={logout}>
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Shipments Panel */}
          <div className="lg:col-span-2 space-y-6">
            {/* Add Shipment Card */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Plus className="h-5 w-5" />
                  <span>Add New Shipment</span>
                </CardTitle>
                <CardDescription>
                  Enter a tracking number to start monitoring your shipment
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex space-x-2">
                  <Input
                    placeholder="Enter tracking number"
                    value={newTrackingNumber}
                    onChange={(e) => setNewTrackingNumber(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && addShipment()}
                  />
                  <Button onClick={addShipment} disabled={addingShipment}>
                    {addingShipment ? 'Adding...' : 'Add'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Shipments List */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center space-x-2">
                      <Package className="h-5 w-5" />
                      <span>Your Shipments ({shipments.length})</span>
                    </CardTitle>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={toggleLiveTracking}
                      className={liveTrackingEnabled ? 'bg-green-50 border-green-200' : ''}
                    >
                      {isConnected ? (
                        <><Wifi className="h-4 w-4 mr-1" />WebSocket Live</>
                      ) : liveTrackingEnabled ? (
                        <><RefreshCw className="h-4 w-4 mr-1" />Polling Mode</>
                      ) : (
                        <><WifiOff className="h-4 w-4 mr-1" />Tracking Off</>
                      )}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {shipments.length === 0 ? (
                  <div className="text-center py-8">
                    <Package className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-500">No shipments found. Add your first tracking number above.</p>
                  </div>
                ) : (
                  <>
                    {/* Search Bar */}
                    <div className="mb-4">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                        <Input
                          placeholder="Search by tracking number..."
                          value={searchTerm}
                          onChange={(e) => setSearchTerm(e.target.value)}
                          className="pl-10"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-4">
                      {filteredShipments.length === 0 ? (
                        <div className="text-center py-4">
                          <p className="text-gray-500">No shipments match your search criteria.</p>
                        </div>
                      ) : (
                        filteredShipments.map((shipment) => (
                          <div key={shipment.id} className={`border rounded-lg p-6 transition-all duration-200 bg-white relative ${
                            updatingShipments.has(shipment.id) ? 'ring-2 ring-blue-200 shadow-lg' : 'hover:shadow-lg'
                          }`}>
                            {/* Live update indicator */}
                            {updatingShipments.has(shipment.id) && (
                              <div className="absolute top-2 right-2">
                                <div className="flex items-center space-x-1 text-xs px-2 py-1 bg-blue-100 text-blue-700 rounded-full">
                                  <div className="animate-spin h-3 w-3 border border-blue-600 rounded-full border-t-transparent"></div>
                                  <span>Updating</span>
                                </div>
                              </div>
                            )}
                            
                            {/* Enhanced Header with Status Icon */}
                            <div className="flex justify-between items-start mb-4">
                              <div className="flex-1">
                                <h3 className="font-bold text-xl text-gray-900 flex items-center space-x-2">
                                  <span>{shipment.tracking_number}</span>
                                  {getStatusIcon(shipment.status)}
                                </h3>
                                {shipment.description && (
                                  <p className="text-sm text-gray-600 mt-1">{shipment.description}</p>
                                )}
                              </div>
                              <div className="flex space-x-2 items-center">
                                {/* Enhanced Status Badge */}
                                <div className={`${getStatusColor(shipment.status)} border font-medium px-3 py-2 rounded-lg flex items-center space-x-1`}>
                                  {getStatusIcon(shipment.status)}
                                  <span>{shipment.status || 'Unknown'}</span>
                                </div>
                                <Button 
                                  variant="outline" 
                                  size="sm"
                                  onClick={() => trackShipment(shipment.tracking_number)}
                                  disabled={updatingShipments.has(shipment.id)}
                                  className="hover:bg-blue-50"
                                >
                                  {updatingShipments.has(shipment.id) ? (
                                    <div className="animate-spin h-4 w-4 border border-gray-400 rounded-full border-t-transparent"></div>
                                  ) : (
                                    <Search className="h-4 w-4" />
                                  )}
                                </Button>
                              </div>
                            </div>
                            
                            {/* Enhanced Progress bar */}
                            {renderEnhancedProgressBar(shipment)}
                            
                            {/* Shipment details grid */}
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm mb-4">
                              {shipment.carrier && (
                                <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                  {getCarrierIcon(shipment.carrier)}
                                  <div>
                                    <p className="text-gray-500 text-xs">Carrier</p>
                                    <p className="font-medium text-gray-900">{shipment.carrier}</p>
                                  </div>
                                </div>
                              )}
                              {shipment.origin && (
                                <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                  <MapPin className="h-5 w-5 text-green-600" />
                                  <div>
                                    <p className="text-gray-500 text-xs">Origin</p>
                                    <p className="font-medium text-gray-900">{shipment.origin}</p>
                                  </div>
                                </div>
                              )}
                              {shipment.destination && (
                                <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                  <MapPin className="h-5 w-5 text-purple-600" />
                                  <div>
                                    <p className="text-gray-500 text-xs">Destination</p>
                                    <p className="font-medium text-gray-900">{shipment.destination}</p>
                                  </div>
                                </div>
                              )}
                              {shipment.estimated_delivery && (
                                <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                  <Calendar className="h-5 w-5 text-orange-600" />
                                  <div>
                                    <p className="text-gray-500 text-xs">Estimated Delivery</p>
                                    <p className="font-medium text-gray-900">
                                      {new Date(shipment.estimated_delivery).toLocaleDateString('en-US', {
                                        weekday: 'short',
                                        year: 'numeric',
                                        month: 'short',
                                        day: 'numeric'
                                      })}
                                    </p>
                                  </div>
                                </div>
                              )}
                              <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                <Clock className="h-5 w-5 text-gray-600" />
                                <div>
                                  <p className="text-gray-500 text-xs">Last Updated</p>
                                  <p className="font-medium text-gray-900">
                                    {new Date(shipment.updated_at).toLocaleDateString('en-US', {
                                      month: 'short',
                                      day: 'numeric',
                                      hour: '2-digit',
                                      minute: '2-digit'
                                    })}
                                  </p>
                                </div>
                              </div>
                            </div>
                            
                            {/* Enhanced Timeline */}
                            <div className="relative">
                              {renderShipmentTimeline(shipment)}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Chat Panel */}
          <div className="lg:col-span-1">
            <Card className="h-[calc(100vh-12rem)] max-h-[700px] min-h-[500px] flex flex-col">
              <CardHeader className="flex-shrink-0 pb-3">
                <CardTitle className="flex items-center space-x-2">
                  <MessageCircle className="h-5 w-5" />
                  <span>Logistics AI Assistant</span>
                </CardTitle>
                <CardDescription className="text-sm">
                  Ask questions about your shipments and logistics
                </CardDescription>
              </CardHeader>
              
              <CardContent className="flex-1 flex flex-col min-h-0 p-4 pt-0">
                {/* Chat Messages Area */}
                <div className="flex-1 overflow-hidden">
                  <ScrollArea className="h-full pr-2">
                    <div className="space-y-3 py-2">
                      {chatMessages.map((message) => (
                        <div
                          key={message.id}
                          className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'} px-1`}
                        >
                          <div
                            className={`max-w-[90%] p-3 rounded-lg shadow-sm ${
                              message.sender === 'user'
                                ? 'bg-blue-600 text-white ml-auto'
                                : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white mr-auto'
                            }`}
                          >
                            <div className="break-words overflow-wrap-anywhere">
                              <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.text}</p>
                              <p className="text-xs opacity-70 mt-1">
                                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                      {chatLoading && (
                        <div className="flex justify-start px-1">
                          <div className="bg-gray-100 dark:bg-gray-700 p-3 rounded-lg shadow-sm">
                            <div className="flex space-x-1 items-center">
                              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                              <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                            </div>
                          </div>
                        </div>
                      )}
                      <div ref={chatEndRef} />
                    </div>
                  </ScrollArea>
                </div>
                
                {/* Input Area */}
                <div className="flex-shrink-0 pt-3 border-t border-gray-200 dark:border-gray-700">
                  <div className="flex space-x-2">
                    <Input
                      placeholder="Ask about your shipments..."
                      value={newMessage}
                      onChange={(e) => setNewMessage(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey && !chatLoading && newMessage.trim()) {
                          e.preventDefault();
                          sendMessage();
                        }
                      }}
                      disabled={chatLoading}
                      className="flex-1 text-sm"
                      maxLength={500}
                    />
                    <Button 
                      onClick={sendMessage} 
                      disabled={chatLoading || !newMessage.trim()}
                      size="sm"
                      className="px-3"
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}