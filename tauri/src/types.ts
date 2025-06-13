// Types for Aya Voice Assistant

// Settings type
export interface AyaSettings {
  videoMode: string;
  audioSource: string;
  language: string;
  voice: string;
  responseModality: string;
  systemPrompt: string;
  model: string;
  initialMessage?: string;
}

// Default settings
export const DEFAULT_SETTINGS: AyaSettings = {
  videoMode: 'none',
  audioSource: 'microphone',
  language: 'English (US)',
  voice: 'Leda (Female)',
  responseModality: 'AUDIO',
  systemPrompt: 'system_prompts/default/aya_default_tools.txt',
  model: 'Gemini 2.0 Flash Live',
  initialMessage: '[CALL_START]'
};

// Resources type
export interface AyaResources {
  systemPrompts: Record<string, string[]>;
  languages: string[];
  voices: string[];
  audioSources: string[];
  videoModes: string[];
  responseModalities: string[];
  models: string[];
  availableChannels: string[];  // Re-enabled dynamic channels
}

// Chat message types
export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant' | 'system' | 'tool';
  message: string;
  timestamp: number;
}

export type TextChannel = string; // Changed to string to support dynamic channels

// WebSocket message types
export interface BaseWebSocketMessage {
  type: string;
  timestamp: number;
}

export interface StatusMessage extends BaseWebSocketMessage {
  type: 'status';
  status: string;
  isRunning: boolean;
  data?: {
    confidence?: number;
    transcription?: string;
    response?: string;
    source?: string;
    text?: string;
    audio?: boolean;
    function?: string;
  };
}

export interface ErrorMessage extends BaseWebSocketMessage {
  type: 'error';
  error: string;
  stackTrace?: string;
}

export interface ResourcesMessage extends BaseWebSocketMessage {
  type: 'resources';
  resources: AyaResources;
}

export interface ChatMessageReceived extends BaseWebSocketMessage {
  type: 'chat_message';
  sender: 'assistant' | 'system' | 'tool';
  message: string;
  channel: TextChannel;
}

export interface LogMessage extends BaseWebSocketMessage {
  type: 'log_message';
  level: 'info' | 'warning' | 'error' | 'debug';
  message: string;
}

// New message type for when a channel is added
export interface ChannelAddedMessage extends BaseWebSocketMessage {
  type: 'channel_added';
  channel: string;
}

export type WebSocketMessage = StatusMessage | ErrorMessage | ResourcesMessage | ChatMessageReceived | LogMessage | ChannelAddedMessage;

// WebSocket command types
export interface BaseWebSocketCommand {
  command: string;
}

export interface StartCommand extends BaseWebSocketCommand {
  command: 'start';
  config: AyaSettings;
}

export interface StopCommand extends BaseWebSocketCommand {
  command: 'stop';
}

export interface GetResourcesCommand extends BaseWebSocketCommand {
  command: 'get_resources';
}

export interface SendMessageCommand extends BaseWebSocketCommand {
  command: 'send_message';
  message: string;
}

export interface ClearChannelCommand extends BaseWebSocketCommand {
  command: 'clear_channel';
  channel: TextChannel;
}

export type WebSocketCommand = StartCommand | StopCommand | GetResourcesCommand | SendMessageCommand | ClearChannelCommand; 