import React from 'react';
import '../styles/VoiceControls.css';

interface VoiceControlsProps {
  isRunning: boolean;
  onStart: () => void;
  onStop: () => void;
  disabled?: boolean;
  isConnecting?: boolean;
  isConnected?: boolean;
}

const VoiceControls: React.FC<VoiceControlsProps> = ({ 
  isRunning, 
  onStart, 
  onStop, 
  disabled = false,
  isConnecting = false,
  isConnected = false
}) => {
  return (
    <div className="voice-controls">
      <button 
        onClick={isRunning ? onStop : onStart}
        className={`control-button ${isRunning ? 'stop' : 'start'}`}
        disabled={disabled}
      >
        {isRunning ? 'Stop Assistant' : 'Start Assistant'}
      </button>
      
      {isConnecting && (
        <p className="controls-connecting-message">
          Connecting to backend...
        </p>
      )}
      
      {disabled && !isConnecting && (
        <p className="controls-disabled-message">
          {!isConnected ? "Backend not connected" : "Fix errors before starting the assistant"}
        </p>
      )}
    </div>
  );
};

export default VoiceControls; 