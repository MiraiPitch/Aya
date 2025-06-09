import { useState, useEffect, useRef, useCallback } from 'react';
import { WebSocketMessage, WebSocketCommand } from '../types';

export const useWebSocket = (url: string) => {
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  // Connect to WebSocket
  const connect = useCallback(() => {
    try {
      console.log(`=== ATTEMPTING WEBSOCKET CONNECTION TO: ${url} ===`);
      const socket = new WebSocket(url);
      
      socket.onopen = () => {
        console.log('=== WEBSOCKET CONNECTED SUCCESSFULLY ===');
        setIsConnected(true);
        setError(null);
        
        // Clear any reconnect timeout
        if (reconnectTimeoutRef.current !== null) {
          window.clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };
      
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketMessage;
          setMessages((prev) => [...prev, data]);
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };
      
      socket.onclose = (event) => {
        console.log(`=== WEBSOCKET DISCONNECTED === Code: ${event.code}, Reason: ${event.reason}`);
        setIsConnected(false);
        
        // Attempt to reconnect after 2 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          console.log('=== ATTEMPTING TO RECONNECT WEBSOCKET ===');
          connect();
        }, 2000);
      };
      
      socket.onerror = (err) => {
        console.error('=== WEBSOCKET ERROR ===', err);
        setError('WebSocket connection error');
      };
      
      socketRef.current = socket;
    } catch (err) {
      console.error('=== ERROR CREATING WEBSOCKET ===', err);
      setError(`Failed to connect to WebSocket: ${err}`);
      
      // Attempt to reconnect after 2 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        console.log('=== ATTEMPTING TO RECONNECT AFTER ERROR ===');
        connect();
      }, 2000);
    }
  }, [url]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  // Send message to WebSocket
  const sendMessage = useCallback((message: WebSocketCommand) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    messages,
    error,
    sendMessage,
    connect,
    disconnect,
  };
};