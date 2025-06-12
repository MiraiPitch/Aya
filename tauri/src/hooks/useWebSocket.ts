import { useState, useEffect, useRef, useCallback } from 'react';
import { WebSocketMessage, WebSocketCommand } from '../types';

export const useWebSocket = (url: string) => {
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(true);
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const retryStartTimeRef = useRef<number | null>(null);
  
  // Configuration for retry mechanism
  const RETRY_TIMEOUT = 15000; // 15 seconds total retry time
  const RETRY_INTERVAL = 500; // 500ms between retries

  // Connect to WebSocket with retry logic
  const connect = useCallback((isRetry = false) => {
    try {
      // Check if there's already a connection
      if (socketRef.current && socketRef.current.readyState !== WebSocket.CLOSED) {
        console.log('=== WEBSOCKET ALREADY EXISTS ===', socketRef.current.readyState);
        return;
      }

      // Initialize retry timer on first attempt
      if (!isRetry) {
        retryStartTimeRef.current = Date.now();
        setError(null); // Clear any previous errors at start
        setIsConnecting(true);
      }
      
      console.log(`=== ATTEMPTING WEBSOCKET CONNECTION TO: ${url} ===`);
      const socket = new WebSocket(url);
      
      socket.onopen = () => {
        console.log('=== WEBSOCKET CONNECTED SUCCESSFULLY ===');
        console.log('=== WEBSOCKET READY STATE ===', socket.readyState);
        setIsConnected(true);
        setIsConnecting(false);
        setError(null);  // Clear any previous errors
        retryStartTimeRef.current = null; // Reset retry timer
        
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
        
        // Check if we should retry or show error
        if (retryStartTimeRef.current && Date.now() - retryStartTimeRef.current < RETRY_TIMEOUT) {
          // Still within retry period, don't show error, just retry
          console.log('=== RETRYING CONNECTION (WITHIN RETRY PERIOD) ===');
          reconnectTimeoutRef.current = window.setTimeout(() => {
            connect(true);
          }, RETRY_INTERVAL);
                 } else if (event.code !== 1000) {
           // Outside retry period or no retry started, show error and attempt single reconnect
           setIsConnecting(false);
           setError(`WebSocket closed: ${closeMessage} (Code: ${event.code}${event.reason ? `, Reason: ${event.reason}` : ''})`);
           reconnectTimeoutRef.current = window.setTimeout(() => {
             console.log('=== ATTEMPTING TO RECONNECT WEBSOCKET ===');
             connect();
           }, 5000);
         } else {
           console.log('=== CLEAN CLOSE - NOT RECONNECTING ===');
           setIsConnecting(false);
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
        
        // Check if we should retry or show error
        if (retryStartTimeRef.current && Date.now() - retryStartTimeRef.current < RETRY_TIMEOUT) {
          // Still within retry period, don't show error, just log and let onclose handle retry
          console.log('=== CONNECTION ERROR DURING RETRY PERIOD - WILL RETRY ===');
                 } else {
           // Outside retry period, show error
           setIsConnecting(false);
           setError(`WebSocket connection error: ${err.type} (ReadyState: ${err.target ? (err.target as WebSocket).readyState : 'unknown'})`);
         }
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
      
      // Check if we should retry or show error
      if (retryStartTimeRef.current && Date.now() - retryStartTimeRef.current < RETRY_TIMEOUT) {
        // Still within retry period, don't show error, just retry
        console.log('=== RETRYING CONNECTION AFTER ERROR (WITHIN RETRY PERIOD) ===');
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect(true);
        }, RETRY_INTERVAL);
             } else {
         // Outside retry period, show error and attempt single reconnect
         setIsConnecting(false);
         setError(`Failed to connect to WebSocket: ${err}`);
         reconnectTimeoutRef.current = window.setTimeout(() => {
           console.log('=== ATTEMPTING TO RECONNECT AFTER ERROR ===');
           connect();
         }, 2000);
       }
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
    
    // Reset retry timer
    retryStartTimeRef.current = null;
    setIsConnecting(false);
  }, []);

  // Send message to WebSocket
  const sendMessage = useCallback((message: WebSocketCommand) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  // Connect immediately on mount, disconnect on unmount
  useEffect(() => {
    console.log('=== STARTING INITIAL WEBSOCKET CONNECTION ===');
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    isConnecting,
    messages,
    error,
    sendMessage,
    connect,
    disconnect,
  };
};