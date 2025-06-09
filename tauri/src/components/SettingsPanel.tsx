import React from 'react';
import '../styles/SettingsPanel.css';
import { AyaSettings, AyaResources } from '../types';

interface SettingsPanelProps {
  settings: AyaSettings;
  resources: AyaResources | null;
  onUpdateSettings: (settings: Partial<AyaSettings>) => void;
  disabled?: boolean;
}

const SettingsPanel: React.FC<SettingsPanelProps> = ({ 
  settings, 
  resources, 
  onUpdateSettings, 
  disabled = false 
}) => {
  const handleChange = (key: keyof AyaSettings, value: any) => {
    onUpdateSettings({ [key]: value });
  };

  // Flatten system prompts for dropdown
  const flattenSystemPrompts = () => {
    if (!resources?.systemPrompts) return [];
    
    const flattened: { value: string; label: string }[] = [];
    
    Object.entries(resources.systemPrompts).forEach(([category, prompts]) => {
      prompts.forEach(prompt => {
        const pathParts = prompt.split('/');
        const filename = pathParts[pathParts.length - 1];
        flattened.push({
          value: prompt,
          label: `${category} - ${filename}`
        });
      });
    });
    
    return flattened;
  };

  return (
    <div className="settings-panel">
      <h2>Settings</h2>
      
      <div className="settings-grid">
        <div className="setting-group">
          <label htmlFor="videoMode">Video Mode:</label>
          <select
            id="videoMode"
            value={settings.videoMode}
            onChange={(e) => handleChange('videoMode', e.target.value)}
            disabled={disabled}
          >
            {resources?.videoModes && Array.isArray(resources.videoModes) ? 
              resources.videoModes.map(mode => (
                <option key={mode} value={mode}>{mode}</option>
              )) : 
              <option value="">Loading...</option>
            }
          </select>
        </div>
        
        <div className="setting-group">
          <label htmlFor="audioSource">Audio Source:</label>
          <select
            id="audioSource"
            value={settings.audioSource}
            onChange={(e) => handleChange('audioSource', e.target.value)}
            disabled={disabled}
          >
            {resources?.audioSources && Array.isArray(resources.audioSources) ? 
              resources.audioSources.map(source => (
                <option key={source} value={source}>{source}</option>
              )) : 
              <option value="">Loading...</option>
            }
          </select>
        </div>
        
        <div className="setting-group">
          <label htmlFor="language">Language:</label>
          <select
            id="language"
            value={settings.language}
            onChange={(e) => handleChange('language', e.target.value)}
            disabled={disabled}
          >
            {resources?.languages && Array.isArray(resources.languages) ? 
              resources.languages.map(lang => (
                <option key={lang} value={lang}>{lang}</option>
              )) : 
              <option value="">Loading...</option>
            }
          </select>
        </div>
        
        <div className="setting-group">
          <label htmlFor="voice">Voice:</label>
          <select
            id="voice"
            value={settings.voice}
            onChange={(e) => handleChange('voice', e.target.value)}
            disabled={disabled}
          >
            {resources?.voices && Array.isArray(resources.voices) ? 
              resources.voices.map(voice => (
                <option key={voice} value={voice}>{voice}</option>
              )) : 
              <option value="">Loading...</option>
            }
          </select>
        </div>
        
        <div className="setting-group">
          <label htmlFor="responseModality">Response Mode:</label>
          <select
            id="responseModality"
            value={settings.responseModality}
            onChange={(e) => handleChange('responseModality', e.target.value)}
            disabled={disabled}
          >
            {resources?.responseModalities && Array.isArray(resources.responseModalities) ? 
              resources.responseModalities.map(modality => (
                <option key={modality} value={modality}>{modality}</option>
              )) : 
              <option value="">Loading...</option>
            }
          </select>
        </div>
        
        <div className="setting-group">
          <label htmlFor="systemPrompt">System Prompt:</label>
          <select
            id="systemPrompt"
            value={settings.systemPrompt}
            onChange={(e) => handleChange('systemPrompt', e.target.value)}
            disabled={disabled}
          >
            {flattenSystemPrompts().map(prompt => (
              <option key={prompt.value} value={prompt.value}>{prompt.label}</option>
            ))}
          </select>
        </div>
      </div>
      
      {disabled && (
        <p className="settings-disabled-message">
          Stop the assistant to change settings
        </p>
      )}
    </div>
  );
};

export default SettingsPanel; 