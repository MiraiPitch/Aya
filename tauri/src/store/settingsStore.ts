import { useState, useEffect } from 'react';
import { BaseDirectory, readTextFile, writeTextFile, exists, createDir } from '@tauri-apps/api/fs';
import { AyaSettings, DEFAULT_SETTINGS } from '../types';

const SETTINGS_FILE = 'settings.json';

// Helper function to read settings from file
const readSettingsFromFile = async (): Promise<AyaSettings> => {
  try {
    // Check if settings file exists
    const fileExists = await exists(SETTINGS_FILE, { dir: BaseDirectory.AppConfig });
    if (!fileExists) {
      return DEFAULT_SETTINGS;
    }
    
    // Read settings from file
    const contents = await readTextFile(SETTINGS_FILE, { dir: BaseDirectory.AppConfig });
    return JSON.parse(contents) as AyaSettings;
  } catch (error) {
    console.error('Error reading settings:', error);
    return DEFAULT_SETTINGS;
  }
};

// Helper function to write settings to file
const writeSettingsToFile = async (settings: AyaSettings): Promise<void> => {
  try {
    // Create config directory if it doesn't exist
    const configDirExists = await exists('', { dir: BaseDirectory.AppConfig });
    if (!configDirExists) {
      await createDir('', { dir: BaseDirectory.AppConfig, recursive: true });
    }
    
    // Write settings to file
    await writeTextFile(SETTINGS_FILE, JSON.stringify(settings, null, 2), { dir: BaseDirectory.AppConfig });
  } catch (error) {
    console.error('Error writing settings:', error);
  }
};

// Hook for managing settings
export const useSettingsStore = () => {
  const [settings, setSettings] = useState<AyaSettings>(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);

  // Load settings on mount
  useEffect(() => {
    const loadSettings = async () => {
      const loadedSettings = await readSettingsFromFile();
      setSettings(loadedSettings);
      setLoaded(true);
    };
    
    loadSettings();
  }, []);

  // Update settings
  const updateSettings = async (newSettings: Partial<AyaSettings>) => {
    const updatedSettings = { ...settings, ...newSettings };
    setSettings(updatedSettings);
    await writeSettingsToFile(updatedSettings);
  };

  return {
    settings,
    updateSettings,
    loaded
  };
}; 