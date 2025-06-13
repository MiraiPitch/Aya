import { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { appWindow } from '@tauri-apps/api/window';
import { 
  AyaResources,
  StartCommand,
  StopCommand,
  GetResourcesCommand,
  SendMessageCommand,
  ClearChannelCommand,
  ChatMessage,
  TextChannel
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
  // Temporarily removing availableChannels state
  // const [availableChannels, setAvailableChannels] = useState<string[]>(['conversation', 'logs', 'status']);
  
  // Chat state management - start with basic channels
  const [messages, setMessages] = useState<Record<TextChannel, ChatMessage[]>>({
    conversation: [],
    logs: [],
    status: []
  });

  // Connect to WebSocket server
  const { 
    isConnected, 
    isConnecting,
    messages: wsMessages, 
    error: wsError, 
    sendMessage 
  } = useWebSocket('ws://127.0.0.1:8765');

  // Helper function to generate message ID
  const generateMessageId = () => {
    return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  };

  // Helper function to add message to a channel
  const addMessageToChannel = useCallback((channel: TextChannel, message: ChatMessage) => {
    setMessages(prev => {
      // Ensure the channel exists in messages
      const updatedMessages = { ...prev };
      if (!updatedMessages[channel]) {
        updatedMessages[channel] = [];
      }
      return {
        ...updatedMessages,
        [channel]: [...updatedMessages[channel], message]
      };
    });
  }, []);

  // Add a new channel if it doesn't exist
  const addChannel = useCallback((channel: string) => {
    // Temporarily removing availableChannels handling
    // setAvailableChannels(prev => {
    //   if (!prev.includes(channel)) {
    //     return [...prev, channel];
    //   }
    //   return prev;
    // });
    
    setMessages(prev => {
      if (!prev[channel]) {
        return {
      ...prev,
          [channel]: []
        };
      }
      return prev;
    });
  }, []);

  // Send a chat message
  const sendChatMessage = useCallback((message: string) => {
    if (!isConnected) {
      console.error('Cannot send message: not connected to WebSocket');
      return;
    }

    // Add user message to conversation channel immediately
    const userMessage: ChatMessage = {
      id: generateMessageId(),
      sender: 'user',
      message,
      timestamp: Date.now()
    };
    addMessageToChannel('conversation', userMessage);

    // Send message to backend
    const sendCommand: SendMessageCommand = {
      command: 'send_message',
      message
    };
    
    const success = sendMessage(sendCommand);
    if (!success) {
      console.error('Failed to send message to backend');
      // Add error message to conversation
      const errorMessage: ChatMessage = {
        id: generateMessageId(),
        sender: 'system',
        message: 'Failed to send message to backend',
        timestamp: Date.now()
      };
      addMessageToChannel('conversation', errorMessage);
    }
  }, [isConnected, sendMessage, addMessageToChannel]);

  // Clear a text channel
  const clearChannel = useCallback((channel: TextChannel) => {
    setMessages(prev => ({
      ...prev,
      [channel]: []
    }));

    // Optionally, send clear command to backend
    const clearCommand: ClearChannelCommand = {
      command: 'clear_channel',
      channel
    };
    sendMessage(clearCommand);
  }, [sendMessage]);

  // Start the voice agent
  const startAgent = useCallback(async () => {
    try {
      console.log('=== START AGENT CALLED ===');
      
      if (isRunning) {
        console.log('=== VOICE AGENT ALREADY RUNNING ===');
        return;
      }
      
      setStatus('starting');
      
      // Add status message
      const statusMessage: ChatMessage = {
        id: generateMessageId(),
        sender: 'system',
        message: 'Starting voice agent...',
        timestamp: Date.now()
      };
      addMessageToChannel('status', statusMessage);
      
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
      
      // Add error message to logs
      const errorMessage: ChatMessage = {
        id: generateMessageId(),
        sender: 'system',
        message: `Error starting voice agent: ${err}`,
        timestamp: Date.now()
      };
      addMessageToChannel('logs', errorMessage);
    }
  }, [isConnected, isRunning, sendMessage, settings, addMessageToChannel]);

  // Stop the voice agent
  const stopAgent = useCallback(async () => {
    try {
      if (!isRunning) {
        console.log('=== VOICE AGENT NOT RUNNING ===');
        return;
      }
      
      setStatus('stopping');
      
      // Add status message
      const statusMessage: ChatMessage = {
        id: generateMessageId(),
        sender: 'system',
        message: 'Stopping voice agent...',
        timestamp: Date.now()
      };
      addMessageToChannel('status', statusMessage);
      
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
      
      // Add error message to logs
      const errorMessage: ChatMessage = {
        id: generateMessageId(),
        sender: 'system',
        message: `Error stopping voice agent: ${err}`,
        timestamp: Date.now()
      };
      addMessageToChannel('logs', errorMessage);
    }
  }, [isConnected, isRunning, sendMessage, addMessageToChannel]);

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
      if (wsMessages.length === 0) return;
      
      const latestMessage = wsMessages[wsMessages.length - 1];
      console.log('=== HANDLING MESSAGE ===', latestMessage);
      
      switch (latestMessage.type) {
        case 'status':
          console.log('=== PROCESSING STATUS MESSAGE ===', latestMessage.status);
          setStatus(latestMessage.status);
          if (latestMessage.isRunning !== undefined) {
            setIsRunning(latestMessage.isRunning);
          }
          
          // Add status to status channel
          const statusMessage: ChatMessage = {
            id: generateMessageId(),
            sender: 'system',
            message: `Status: ${latestMessage.status}`,
            timestamp: latestMessage.timestamp
          };
          addMessageToChannel('status', statusMessage);
          break;
          
        case 'error':
          console.log('=== PROCESSING ERROR MESSAGE ===', latestMessage.error);
          setError(latestMessage.error);
          setStatus('error');
          
          // Add error to logs channel
          const errorMessage: ChatMessage = {
            id: generateMessageId(),
            sender: 'system',
            message: `Error: ${latestMessage.error}`,
            timestamp: latestMessage.timestamp
          };
          addMessageToChannel('logs', errorMessage);
          break;
          
        case 'resources':
          console.log('=== PROCESSING RESOURCES MESSAGE ===', latestMessage.resources);
          console.log('=== WEBSOCKET CONNECTION STATE BEFORE SETTING RESOURCES ===', isConnected);
          console.log('=== DETAILED RESOURCES CONTENT ===', {
            systemPrompts: latestMessage.resources?.systemPrompts,
            languages: latestMessage.resources?.languages,
            voices: latestMessage.resources?.voices,
            audioSources: latestMessage.resources?.audioSources,
            videoModes: latestMessage.resources?.videoModes,
            responseModalities: latestMessage.resources?.responseModalities,
            availableChannels: latestMessage.resources?.availableChannels
          });
          setResources(latestMessage.resources);
          
          // Temporarily removing availableChannels handling
          /*
          // Update available channels from resources
          if (latestMessage.resources.availableChannels) {
            setAvailableChannels(latestMessage.resources.availableChannels);
            
            // Initialize message arrays for new channels
            latestMessage.resources.availableChannels.forEach(channel => {
              setMessages(prev => {
                if (!prev[channel]) {
                  return {
                    ...prev,
                    [channel]: []
                  };
                }
                return prev;
              });
            });
          }
          */
          
          console.log('=== RESOURCES SET, CHECKING CONNECTION STATE ===', isConnected);
          break;
          
        case 'chat_message':
          console.log('=== PROCESSING CHAT MESSAGE ===', latestMessage);
          
          // Add the channel if it doesn't exist
          addChannel(latestMessage.channel);
          
          const chatMessage: ChatMessage = {
            id: generateMessageId(),
            sender: latestMessage.sender,
            message: latestMessage.message,
            timestamp: latestMessage.timestamp
          };
          addMessageToChannel(latestMessage.channel, chatMessage);
          break;
          
        case 'log_message':
          console.log('=== PROCESSING LOG MESSAGE ===', latestMessage);
          const logMessage: ChatMessage = {
            id: generateMessageId(),
            sender: 'system',
            message: `[${latestMessage.level.toUpperCase()}] ${latestMessage.message}`,
            timestamp: latestMessage.timestamp
          };
          addMessageToChannel('logs', logMessage);
          break;
          
        case 'channel_added':
          console.log('=== PROCESSING CHANNEL ADDED MESSAGE ===', latestMessage);
          addChannel(latestMessage.channel);
          
          // Add a system message to the logs about the new channel
          const channelAddedMessage: ChatMessage = {
            id: generateMessageId(),
            sender: 'system',
            message: `New channel added: ${latestMessage.channel}`,
            timestamp: latestMessage.timestamp
          };
          addMessageToChannel('logs', channelAddedMessage);
          break;
          
        default:
          console.log('=== UNKNOWN MESSAGE TYPE ===', (latestMessage as any).type);
          break;
      }
    };
    
    handleMessages();
  }, [wsMessages, addMessageToChannel, isConnected, addChannel]);

  // Set WebSocket error
  useEffect(() => {
    if (wsError) {
      console.log('=== SETTING WEBSOCKET ERROR ===', wsError);
      setError(wsError);
      
      // Add WebSocket error to logs
      const errorMessage: ChatMessage = {
        id: generateMessageId(),
        sender: 'system',
        message: `WebSocket error: ${wsError}`,
        timestamp: Date.now()
      };
      addMessageToChannel('logs', errorMessage);
    }
  }, [wsError, addMessageToChannel]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isConnected, fetchResources]);

  return {
    isRunning,
    status,
    error,
    settings,
    resources,
    messages,
    // Temporarily removing availableChannels from return
    // availableChannels,
    availableChannels: ['conversation', 'logs', 'status'], // Hardcode for now
    startAgent,
    stopAgent,
    updateSettings,
    clearError,
    sendChatMessage,
    clearChannel,
    isLoaded: loaded,
    isConnected,
    isConnecting,
    wsError
  };
}; 