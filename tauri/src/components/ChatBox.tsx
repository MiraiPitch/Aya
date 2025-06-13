import React, { useState, useRef, useEffect, useMemo } from 'react';
import '../styles/ChatBox.css';
import { ChatMessage, TextChannel } from '../types';

interface ChatBoxProps {
  messages: Record<TextChannel, ChatMessage[]>;
  onSendMessage: (message: string) => void;
  onClearChannel: (channel: TextChannel) => void;
  disabled?: boolean;
  isConnected?: boolean;
  availableChannels?: string[];  // Dynamic channels from backend
}

const ChatBox: React.FC<ChatBoxProps> = ({ 
  messages, 
  onSendMessage, 
  onClearChannel, 
  disabled = false,
  isConnected = false,
  availableChannels = ["conversation", "logs", "status"]  // Default initial channels
}) => {
  const [currentChannel, setCurrentChannel] = useState<TextChannel>('conversation');
  const [inputMessage, setInputMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Create channel options from available channels
  const channels = useMemo(() => {
    const channelMap: Record<string, string> = {
      'conversation': 'Conversation',
      'logs': 'Logs',
      'status': 'Status'
    };

    return availableChannels.map(channel => ({
      value: channel as TextChannel,
      label: channelMap[channel] || channel.charAt(0).toUpperCase() + channel.slice(1)
    }));
  }, [availableChannels]);

  const currentMessages = useMemo(() => messages[currentChannel] || [], [messages, currentChannel]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentMessages]);

  // Switch to first available channel if current channel is no longer available
  useEffect(() => {
    if (!availableChannels.includes(currentChannel) && availableChannels.length > 0) {
      setCurrentChannel(availableChannels[0] as TextChannel);
    }
  }, [availableChannels, currentChannel]);

  const handleSendMessage = () => {
    const trimmedMessage = inputMessage.trim();
    if (trimmedMessage && !disabled && isConnected) {
      onSendMessage(trimmedMessage);
      setInputMessage('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleClearChannel = () => {
    onClearChannel(currentChannel);
  };

  const formatTimestamp = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    });
  };

  const getSenderDisplayName = (sender: ChatMessage['sender']) => {
    switch (sender) {
      case 'user': return 'You';
      case 'assistant': return 'Aya';
      case 'system': return 'System';
      case 'tool': return 'Tool';
      default: return sender;
    }
  };

  const getSenderClass = (sender: ChatMessage['sender']) => {
    return `message-${sender}`;
  };

  return (
    <div className="chatbox">
      <div className="chatbox-header">
        <select 
          value={currentChannel} 
          onChange={(e) => setCurrentChannel(e.target.value as TextChannel)}
          className="channel-selector"
        >
          {channels.map(channel => (
            <option key={channel.value} value={channel.value}>
              {channel.label}
            </option>
          ))}
        </select>
        
        <button 
          onClick={handleClearChannel}
          className="clear-button"
          title={`Clear ${channels.find(c => c.value === currentChannel)?.label} channel`}
        >
          Clear
        </button>
      </div>

      <div className="messages-container">
        {currentMessages.length === 0 ? (
          <div className="no-messages">
            No messages in {channels.find(c => c.value === currentChannel)?.label.toLowerCase()} channel
          </div>
        ) : (
          currentMessages.map((message) => (
            <div key={message.id} className={`message ${getSenderClass(message.sender)}`}>
              <div className="message-header">
                <span className="message-sender">{getSenderDisplayName(message.sender)}</span>
                <span className="message-timestamp">{formatTimestamp(message.timestamp)}</span>
              </div>
              <div className="message-content">{message.message}</div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {currentChannel === 'conversation' && (
        <div className="input-container">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={disabled ? "Connect to start messaging..." : "Type a message..."}
            className="message-input"
            disabled={disabled || !isConnected}
            rows={2}
          />
          <button 
            onClick={handleSendMessage}
            disabled={disabled || !isConnected || !inputMessage.trim()}
            className="send-button"
          >
            Send
          </button>
        </div>
      )}

      {!isConnected && (
        <div className="connection-status">
          Not connected to backend
        </div>
      )}
    </div>
  );
};

export default ChatBox; 