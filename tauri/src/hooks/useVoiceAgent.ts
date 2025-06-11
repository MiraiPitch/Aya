import { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
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
    isConnecting,
    messages, 
    error: wsError, 
    sendMessage 
  } = useWebSocket('ws://localhost:8765');

  // Start the voice agent
  const startAgent = useCallback(async () => {
    try {
      console.log('=== START AGENT CALLED ===');
      
      if (isRunning) {
        console.log('=== VOICE AGENT ALREADY RUNNING ===');
        return;
      }
      
      setStatus('starting');
      
      // Check if WebSocket is connected
      if (!isConnected) {
        throw new Error('Not connected to Python bridge. Please wait for connection.');
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
      
      console.log('=== START COMMAND SENT VIA WEBSOCKET ===');
      
    } catch (err) {
      console.error('Error starting voice agent:', err);
      setError(`Failed to start voice agent: ${err}`);
      setStatus('error');
    }
  }, [isConnected, isRunning, sendMessage, settings]);

  // Stop the voice agent
  const stopAgent = useCallback(async () => {
    try {
      if (!isRunning) {
        console.log('=== VOICE AGENT NOT RUNNING ===');
        return;
      }
      
      setStatus('stopping');
      
      // Check if WebSocket is connected
      if (!isConnected) {
        throw new Error('Not connected to Python bridge. Cannot send stop command.');
      }
      
      // Send stop command via WebSocket
      const stopCommand: StopCommand = {
        command: 'stop'
      };
      
      const success = sendMessage(stopCommand);
      if (!success) {
        throw new Error('Failed to send stop command to Python bridge');
      }
      
      console.log('=== STOP COMMAND SENT VIA WEBSOCKET ===');
      
    } catch (err) {
      console.error('Error stopping voice agent:', err);
      setError(`Failed to stop voice agent: ${err}`);
    }
  }, [isConnected, isRunning, sendMessage]);

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

  // Listen for Python bridge status updates (but don't set voice agent running state)
  useEffect(() => {
    if (!isTauri) {
      console.log('=== NOT IN TAURI CONTEXT - SKIPPING BRIDGE EVENT LISTENER ===');
      return;
    }
    
    const unsubscribe = appWindow.listen('python-bridge-status', (event) => {
      const bridgeIsRunning = event.payload as boolean;
      console.log('=== PYTHON BRIDGE STATUS UPDATE ===', bridgeIsRunning);
      
      // Don't set voice agent running state based on bridge status
      // The voice agent running state should only be controlled by WebSocket status messages
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

  // Check if Python bridge is running on mount (but don't set voice agent state)
  useEffect(() => {
    if (!isTauri) {
      console.log('=== NOT IN TAURI CONTEXT - SKIPPING BRIDGE STATUS CHECK ===');
      return;
    }
    
    const checkBridgeStatus = async () => {
      try {
        const bridgeRunning = await invoke<boolean>('is_python_bridge_running');
        console.log('=== PYTHON BRIDGE RUNNING STATUS ===', bridgeRunning);
        
        // Don't set voice agent running state based on bridge status
        // The voice agent running state should only be controlled by WebSocket status messages
        
        // If bridge is running but we're not connected, wait a bit and try again
        if (bridgeRunning && !isConnected) {
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
    isLoaded: loaded,
    isConnected,
    isConnecting,
    wsError
  };
}; 