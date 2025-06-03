import React from 'react';
import './styles/App.css';
import StatusDisplay from './components/StatusDisplay';
import VoiceControls from './components/VoiceControls';
import SettingsPanel from './components/SettingsPanel';
import { useVoiceAgent } from './hooks/useVoiceAgent';

function App() {
  const {
    isRunning,
    status,
    error,
    settings,
    resources,
    startAgent,
    stopAgent,
    updateSettings,
    clearError
  } = useVoiceAgent();

  return (
    <div className="app">
      <header className="app-header">
        <h1>Aya Voice Assistant</h1>
        <StatusDisplay status={status} isRunning={isRunning} />
      </header>
      
      <main className="app-main">
        {error && (
          <div className="error-panel">
            <h3>Error</h3>
            <p>{error}</p>
            <button onClick={clearError}>Dismiss</button>
          </div>
        )}
        
        <VoiceControls 
          isRunning={isRunning} 
          onStart={startAgent} 
          onStop={stopAgent} 
          disabled={!!error} 
        />
        
        <SettingsPanel 
          settings={settings} 
          resources={resources} 
          onUpdateSettings={updateSettings} 
          disabled={isRunning} 
        />
      </main>
      
      <footer className="app-footer">
        <p>Aya Voice Assistant &copy; 2023 MiraiPitch</p>
      </footer>
    </div>
  );
}

export default App; 