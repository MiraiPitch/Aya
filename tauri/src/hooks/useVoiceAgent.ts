import { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { appWindow } from '@tauri-apps/api/window';
import { 
  AyaResources,
  StartCommand,
  StopCommand,
  GetResourcesCommand
} from '../types';
import { useWebSocket } from './useWebSocket';
import { useSettingsStore } from '../store/settingsStore';

// Check if running in Tauri context
const isTauri = typeof window !== 'undefined' && (window as any).__TAURI__ !== undefined;

export const useVoiceAgent = () => {
  const { settings, updateSettings, loaded } = useSettingsStore();
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState<string | null>(null);
  const [resources, setResources] = useState<AyaResources | null>(null);

  // Connect to WebSocket server
  const { 
    isConnected, 
    messages, 
    error: wsError, 
    sendMessage 
  } = useWebSocket('ws://localhost:8765');

  // Start the voice agent
  const startAgent = useCallback(async () => {
    try {
      console.log('=== START AGENT CALLED ===');
      console.log('=== IS TAURI CONTEXT ===', isTauri);
      console.log('=== INVOKE FUNCTION ===', typeof invoke, invoke);
      
      // First start the Python bridge if not running
      if (!isRunning) {
        setStatus('starting');
        
        // Check if running in Tauri context
        if (!isTauri) {
          throw new Error('This app must be run in Tauri context, not in a browser');
        }
        
        // Check if invoke is available
        if (typeof invoke !== 'function') {
          throw new Error('Tauri invoke function is not available');
        }
        
        // Start the Python bridge via Tauri
        console.log('=== CALLING TAURI INVOKE ===');
        await invoke('start_python_bridge');
        
        // Wait for WebSocket connection
        if (!isConnected) {
          // Wait up to 5 seconds for connection
          let attempts = 0;
          while (!isConnected && attempts < 10) {
            await new Promise(resolve => setTimeout(resolve, 500));
            attempts++;
          }
          
          if (!isConnected) {
            throw new Error('Failed to connect to Python bridge');
          }
        }
        
        // Send start command via WebSocket
        const startCommand: StartCommand = {
          command: 'start',
          config: settings
        };
        
        const success = sendMessage(startCommand);
        if (!success) {
          throw new Error('Failed to send start command to Python bridge');
        }
        
        setIsRunning(true);
      }
    } catch (err) {
      console.error('Error starting voice agent:', err);
      setError(`Failed to start voice agent: ${err}`);
      setStatus('error');
    }
  }, [isConnected, isRunning, sendMessage, settings]);

  // Stop the voice agent
  const stopAgent = useCallback(async () => {
    try {
      if (isRunning) {
        setStatus('stopping');
        
        // Send stop command via WebSocket
        const stopCommand: StopCommand = {
          command: 'stop'
        };
        
        const success = sendMessage(stopCommand);
        if (!success) {
          // Try to stop directly via Tauri if WebSocket fails
          await invoke('stop_python_bridge');
        }
        
        setIsRunning(false);
        setStatus('idle');
      }
    } catch (err) {
      console.error('Error stopping voice agent:', err);
      setError(`Failed to stop voice agent: ${err}`);
    }
  }, [isRunning, sendMessage]);

  // Request resources from the Python bridge
  const fetchResources = useCallback(() => {
    if (isConnected) {
      const getResourcesCommand: GetResourcesCommand = {
        command: 'get_resources'
      };
      sendMessage(getResourcesCommand);
    }
  }, [isConnected, sendMessage]);

  // Clear any error messages
  const clearError = useCallback(() => {
    console.log('=== CLEARING ERROR ===');
    setError(null);
  }, []);

  // Listen for Python bridge status updates
  useEffect(() => {
    if (!isTauri) {
      console.log('=== NOT IN TAURI CONTEXT - SKIPPING BRIDGE EVENT LISTENER ===');
      return;
    }
    
    const unsubscribe = appWindow.listen('python-bridge-status', (event) => {
      const isRunning = event.payload as boolean;
      setIsRunning(isRunning);
      
      if (!isRunning) {
        setStatus('idle');
      }
    });
    
    return () => {
      unsubscribe.then(fn => fn());
    };
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    const handleMessages = () => {
      if (messages.length === 0) return;
      
      const latestMessage = messages[messages.length - 1];
      console.log('=== HANDLING MESSAGE ===', latestMessage);
      
      switch (latestMessage.type) {
        case 'status':
          console.log('=== PROCESSING STATUS MESSAGE ===', latestMessage.status);
          setStatus(latestMessage.status);
          if (latestMessage.isRunning !== undefined) {
            setIsRunning(latestMessage.isRunning);
          }
          break;
          
        case 'error':
          console.log('=== PROCESSING ERROR MESSAGE ===', latestMessage.error);
          setError(latestMessage.error);
          setStatus('error');
          break;
          
        case 'resources':
          console.log('=== PROCESSING RESOURCES MESSAGE ===', latestMessage.resources);
          console.log('=== WEBSOCKET CONNECTION STATE BEFORE SETTING RESOURCES ===', isConnected);
          setResources(latestMessage.resources);
          console.log('=== RESOURCES SET, CHECKING CONNECTION STATE ===', isConnected);
          break;
          
        default:
          console.log('=== UNKNOWN MESSAGE TYPE ===', (latestMessage as any).type);
          break;
      }
    };
    
    handleMessages();
  }, [messages]);

  // Set WebSocket error
  useEffect(() => {
    if (wsError) {
      console.log('=== SETTING WEBSOCKET ERROR ===', wsError);
      setError(wsError);
    }
  }, [wsError]);

  // Fetch resources when connected
  useEffect(() => {
    console.log('=== FETCH RESOURCES EFFECT ===', { isConnected, hasResources: !!resources });
    if (isConnected && !resources) {
      console.log('=== CALLING FETCH RESOURCES ===');
      fetchResources();
    }
  }, [isConnected, resources, fetchResources]);

  // Check if Python bridge is running on mount
  useEffect(() => {
    if (!isTauri) {
      console.log('=== NOT IN TAURI CONTEXT - SKIPPING BRIDGE STATUS CHECK ===');
      return;
    }
    
    const checkBridgeStatus = async () => {
      try {
        const running = await invoke<boolean>('is_python_bridge_running');
        setIsRunning(running);
        
        // If bridge is running but we're not connected, wait a bit and try again
        if (running && !isConnected) {
          console.log('=== PYTHON BRIDGE RUNNING BUT NOT CONNECTED, WAITING FOR CONNECTION ===');
          setTimeout(() => {
            if (!isConnected) {
              console.log('=== STILL NOT CONNECTED, CHECKING AGAIN ===');
              fetchResources();
            }
          }, 2000);
        }
      } catch (err) {
        console.error('Error checking Python bridge status:', err);
      }
    };
    
    checkBridgeStatus();
  }, [isConnected, fetchResources, isTauri]);

  return {
    isRunning,
    status,
    error,
    settings,
    resources,
    startAgent,
    stopAgent,
    updateSettings,
    clearError,
    isLoaded: loaded
  };
}; 