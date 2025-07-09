import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
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
  Clock
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

interface ChatMessage {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

export default function Dashboard() {
  const { user, logout, token } = useAuth();
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

  useEffect(() => {
    fetchShipments();
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
    try {
      const response = await fetch(`${API_BASE_URL}/api/track/${trackingNumber}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        toast.success('Tracking information updated');
        fetchShipments();
      } else {
        toast.error('Failed to track shipment');
      }
    } catch (error) {
      toast.error('Error tracking shipment');
    }
  };

  const sendMessage = async () => {
    if (!newMessage.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: newMessage,
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
        body: JSON.stringify({ message: newMessage }),
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
        toast.error('Failed to send message');
      }
    } catch (error) {
      toast.error('Error sending message');
    } finally {
      setChatLoading(false);
    }
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
                <CardTitle className="flex items-center space-x-2">
                  <Package className="h-5 w-5" />
                  <span>Your Shipments ({shipments.length})</span>
                </CardTitle>
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
                          <div key={shipment.id} className="border rounded-lg p-6 hover:shadow-lg transition-all duration-200 bg-white">
                            {/* Header with tracking number and actions */}
                            <div className="flex justify-between items-start mb-4">
                              <div className="flex-1">
                                <h3 className="font-bold text-xl text-gray-900">{shipment.tracking_number}</h3>
                                {shipment.description && (
                                  <p className="text-sm text-gray-600 mt-1">{shipment.description}</p>
                                )}
                              </div>
                              <div className="flex space-x-2 items-center">
                                <Badge className={`${getStatusColor(shipment.status)} border font-medium px-3 py-1`}>
                                  {shipment.status || 'Unknown'}
                                </Badge>
                                <Button 
                                  variant="outline" 
                                  size="sm"
                                  onClick={() => trackShipment(shipment.tracking_number)}
                                  className="hover:bg-blue-50"
                                >
                                  <Search className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                            
                            {/* Progress bar */}
                            <div className="mb-4">
                              <div className="flex justify-between text-xs text-gray-500 mb-1">
                                <span>Progress</span>
                                <span>{getStatusProgress(shipment.status)}%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div 
                                  className={`h-2 rounded-full transition-all duration-300 ${
                                    shipment.status?.toLowerCase() === 'delivered' ? 'bg-green-500' :
                                    shipment.status?.toLowerCase().includes('delayed') || shipment.status?.toLowerCase() === 'exception' ? 'bg-red-500' :
                                    'bg-blue-500'
                                  }`}
                                  style={{ width: `${getStatusProgress(shipment.status)}%` }}
                                ></div>
                              </div>
                            </div>
                            
                            {/* Shipment details grid */}
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
                              {shipment.carrier && (
                                <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                                  <Truck className="h-5 w-5 text-blue-600" />
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
            <Card className="h-[600px] flex flex-col">
              <CardHeader className="flex-shrink-0">
                <CardTitle className="flex items-center space-x-2">
                  <MessageCircle className="h-5 w-5" />
                  <span>Logistics AI Assistant</span>
                </CardTitle>
                <CardDescription>
                  Ask questions about your shipments and logistics
                </CardDescription>
              </CardHeader>
              
              <CardContent className="flex-1 flex flex-col min-h-0">
                <ScrollArea className="flex-1 pr-4 mb-4">
                  <div className="space-y-4 pb-4">
                    {chatMessages.map((message) => (
                      <div
                        key={message.id}
                        className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[85%] p-3 rounded-lg break-words ${
                            message.sender === 'user'
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                          }`}
                        >
                          <p className="text-sm whitespace-pre-wrap">{message.text}</p>
                          <p className="text-xs opacity-70 mt-1">
                            {message.timestamp.toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                    ))}
                    {chatLoading && (
                      <div className="flex justify-start">
                        <div className="bg-gray-100 dark:bg-gray-700 p-3 rounded-lg">
                          <div className="flex space-x-1">
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
                
                <Separator className="my-2" />
                
                <div className="flex space-x-2 flex-shrink-0">
                  <Input
                    placeholder="Ask about your shipments..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                    disabled={chatLoading}
                    className="flex-1"
                  />
                  <Button onClick={sendMessage} disabled={chatLoading || !newMessage.trim()}>
                    <Send className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}