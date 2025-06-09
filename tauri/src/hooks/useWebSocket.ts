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
      // Check if there's already a connection
      if (socketRef.current && socketRef.current.readyState !== WebSocket.CLOSED) {
        console.log('=== WEBSOCKET ALREADY EXISTS ===', socketRef.current.readyState);
        return;
      }
      
      console.log(`=== ATTEMPTING WEBSOCKET CONNECTION TO: ${url} ===`);
      const socket = new WebSocket(url);
      
      socket.onopen = () => {
        console.log('=== WEBSOCKET CONNECTED SUCCESSFULLY ===');
        console.log('=== WEBSOCKET READY STATE ===', socket.readyState);
        setIsConnected(true);
        setError(null);  // Clear any previous errors
        
        // Clear any reconnect timeout
        if (reconnectTimeoutRef.current !== null) {
          window.clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = null;
        }
      };
      
      socket.onmessage = (event) => {
        try {
          console.log('=== RECEIVED WEBSOCKET MESSAGE ===', event.data);
          const data = JSON.parse(event.data) as WebSocketMessage;
          console.log('=== PARSED MESSAGE ===', data);
          
          // Add the message to the queue
          setMessages((prev) => [...prev, data]);
          
          // Log connection state after receiving message
          console.log('=== WEBSOCKET STATE AFTER MESSAGE ===', {
            readyState: socket.readyState,
            bufferedAmount: socket.bufferedAmount
          });
          
        } catch (err) {
          console.error('=== ERROR PARSING WEBSOCKET MESSAGE ===', err);
          console.error('Raw message data:', event.data);
          setError(`Message parsing error: ${err instanceof Error ? err.message : 'Unknown error'}`);
        }
      };
      
      socket.onclose = (event) => {
        console.log(`=== WEBSOCKET DISCONNECTED === Code: ${event.code}, Reason: ${event.reason}, WasClean: ${event.wasClean}`);
        console.log('Close event details:', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          type: event.type
        });
        
        // Map close codes to human-readable messages
        const closeCodeMessages: { [key: number]: string } = {
          1000: 'Normal closure',
          1001: 'Going away',
          1002: 'Protocol error',
          1003: 'Unsupported data',
          1005: 'No status received',
          1006: 'Abnormal closure',
          1007: 'Invalid frame payload data',
          1008: 'Policy violation',
          1009: 'Message too big',
          1010: 'Mandatory extension',
          1011: 'Internal server error',
          1015: 'TLS handshake'
        };
        
        const closeMessage = closeCodeMessages[event.code] || `Unknown close code: ${event.code}`;
        console.log(`=== CLOSE CODE MEANING: ${closeMessage} ===`);
        
        setIsConnected(false);
        setError(`WebSocket closed: ${closeMessage} (Code: ${event.code}${event.reason ? `, Reason: ${event.reason}` : ''})`);
        
        // Only attempt to reconnect if it wasn't a clean close
        if (event.code !== 1000) {
          // Attempt to reconnect after 5 seconds (longer delay to avoid conflicts)
          reconnectTimeoutRef.current = window.setTimeout(() => {
            console.log('=== ATTEMPTING TO RECONNECT WEBSOCKET ===');
            connect();
          }, 5000);
        } else {
          console.log('=== CLEAN CLOSE - NOT RECONNECTING ===');
        }
      };
      
      socket.onerror = (err) => {
        console.error('=== WEBSOCKET ERROR ===', err);
        console.error('Error event details:', {
          type: err.type,
          target: err.target,
          currentTarget: err.currentTarget,
          readyState: err.target ? (err.target as WebSocket).readyState : 'unknown'
        });
        setError(`WebSocket connection error: ${err.type} (ReadyState: ${err.target ? (err.target as WebSocket).readyState : 'unknown'})`);
      };
      
      // Close any existing connection
      if (socketRef.current) {
        console.log('=== CLOSING EXISTING WEBSOCKET ===');
        socketRef.current.close();
      }
      
      socketRef.current = socket;
      console.log('=== WEBSOCKET REFERENCE SET ===', socket.readyState);
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