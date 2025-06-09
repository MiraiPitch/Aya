import { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { appWindow } from '@tauri-apps/api/window';
import { 
  AyaSettings, 
  AyaResources,
  StartCommand,
  StopCommand,
  GetResourcesCommand
} from '../types';
import { useWebSocket } from './useWebSocket';
import { useSettingsStore } from '../store/settingsStore';

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
      // First start the Python bridge if not running
      if (!isRunning) {
        setStatus('starting');
        
        // Start the Python bridge via Tauri
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
    setError(null);
  }, []);

  // Listen for Python bridge status updates
  useEffect(() => {
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
      
      switch (latestMessage.type) {
        case 'status':
          setStatus(latestMessage.status);
          if (latestMessage.isRunning !== undefined) {
            setIsRunning(latestMessage.isRunning);
          }
          break;
          
        case 'error':
          setError(latestMessage.error);
          setStatus('error');
          break;
          
        case 'resources':
          setResources(latestMessage.resources);
          break;
      }
    };
    
    handleMessages();
  }, [messages]);

  // Set WebSocket error
  useEffect(() => {
    if (wsError) {
      setError(wsError);
    }
  }, [wsError]);

  // Fetch resources when connected
  useEffect(() => {
    if (isConnected && !resources) {
      fetchResources();
    }
  }, [isConnected, resources, fetchResources]);

  // Check if Python bridge is running on mount
  useEffect(() => {
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
  }, [isConnected, fetchResources]);

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