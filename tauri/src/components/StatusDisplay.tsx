import React from 'react';
import '../styles/StatusDisplay.css';

interface StatusDisplayProps {
  status: string;
  isRunning: boolean;
}

const StatusDisplay: React.FC<StatusDisplayProps> = ({ status, isRunning }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'listening': return '#4CAF50'; // Green
      case 'processing': return '#FF9800'; // Orange
      case 'speaking': return '#2196F3'; // Blue
      case 'starting': return '#9C27B0'; // Purple
      case 'stopping': return '#FFC107'; // Amber
      case 'error': return '#F44336'; // Red
      default: return '#9E9E9E'; // Grey
    }
  };

  const getStatusText = () => {
    if (!isRunning) return 'Stopped';
    return status.charAt(0).toUpperCase() + status.slice(1);
  };

  return (
    <div className="status-display">
      <div 
        className="status-indicator"
        style={{ backgroundColor: getStatusColor() }}
      />
      <span className="status-text">
        {getStatusText()}
      </span>
    </div>
  );
};

export default StatusDisplay; 