import React from 'react';
import '../styles/VoiceControls.css';

interface VoiceControlsProps {
  isRunning: boolean;
  onStart: () => void;
  onStop: () => void;
  disabled?: boolean;
}

const VoiceControls: React.FC<VoiceControlsProps> = ({ 
  isRunning, 
  onStart, 
  onStop, 
  disabled = false 
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
      
      {disabled && (
        <p className="controls-disabled-message">
          Fix errors before starting the assistant
        </p>
      )}
    </div>
  );
};

export default VoiceControls; 