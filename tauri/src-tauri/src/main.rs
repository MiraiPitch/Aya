#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use std::process::{Command, Stdio};
use std::sync::{Arc, Mutex};
use std::env;
use tauri::{
    Manager, WindowEvent, State, AppHandle, Window
};

// State struct to manage the Python process
struct PythonBridgeState {
    process: Option<std::process::Child>,
    is_running: bool,
}

impl PythonBridgeState {
    fn new() -> Self {
        Self {
            process: None,
            is_running: false,
        }
    }
}

// Direct function to start the Python bridge (for auto-start)
async fn start_python_bridge_direct(
    state: Arc<Mutex<PythonBridgeState>>,
    app_handle: AppHandle,
    window: Window,
) -> Result<String, String> {
    println!("=== START_PYTHON_BRIDGE_DIRECT CALLED ===");
    let mut state_guard = state.lock().unwrap();
    
    // Check if bridge is already running
    if state_guard.is_running {
        println!("=== BRIDGE ALREADY RUNNING ===");
        return Err("Python bridge is already running".to_string());
    }
    
    // Get the path to the Python executable (bundled or installed)
    println!("=== GETTING PYTHON COMMAND ===");
    let (cmd, args) = get_python_command(&app_handle).map_err(|e| e.to_string())?;
    println!("=== PYTHON COMMAND: {} ARGS: {:?} ===", cmd, args);
    
    // Build the command
    let mut command = Command::new(cmd);
    
    // Add arguments if any
    if let Some(args_vec) = args {
        command.args(args_vec);
    }
    
    // Set environment variables if needed
    if let Ok(api_key) = env::var("GEMINI_API_KEY") {
        command.env("GEMINI_API_KEY", api_key);
    }
    
    // Configure stdout and stderr to inherit so we can see output
    command.stdout(Stdio::inherit());
    command.stderr(Stdio::inherit());
    
    // Set working directory to the project root 
    if let Some(current_dir) = std::env::current_dir().ok() {
        println!("=== SETTING WORKING DIRECTORY: {:?} ===", current_dir);
        command.current_dir(current_dir);
    }
    
    // Start the process
    println!("=== SPAWNING PYTHON PROCESS ===");
    match command.spawn() {
        Ok(mut process) => {
            println!("=== PYTHON BRIDGE PROCESS STARTED SUCCESSFULLY ===");
            println!("Process ID: {}", process.id());
            
            // Check if process is still running after a short delay
            std::thread::sleep(std::time::Duration::from_millis(500));
            match process.try_wait() {
                Ok(Some(status)) => {
                    println!("=== PYTHON PROCESS EXITED EARLY WITH STATUS: {:?} ===", status);
                    return Err(format!("Python bridge exited immediately with status: {:?}", status));
                },
                Ok(None) => {
                    println!("=== PYTHON PROCESS STILL RUNNING ===");
                },
                Err(e) => {
                    println!("=== ERROR CHECKING PYTHON PROCESS STATUS: {} ===", e);
                }
            }
            
            state_guard.process = Some(process);
            state_guard.is_running = true;
            
            // Emit event to frontend using the window object
            let _ = window.emit("python-bridge-status", true);
            
            Ok("Python bridge started successfully".to_string())
        },
        Err(e) => {
            println!("=== FAILED TO START PYTHON PROCESS: {} ===", e);
            Err(format!("Failed to start Python bridge: {}", e))
        }
    }
}

// Internal function to start the Python bridge (for commands)
async fn start_python_bridge_internal(
    state: State<'_, Arc<Mutex<PythonBridgeState>>>,
    app_handle: AppHandle,
    window: Window,
) -> Result<String, String> {
    println!("=== START_PYTHON_BRIDGE_INTERNAL CALLED ===");
    // Use the direct function with the Arc from the state
    start_python_bridge_direct(Arc::clone(&state.inner()), app_handle, window).await
}

// Command to start the Python bridge
#[tauri::command]
async fn start_python_bridge(
    state: State<'_, Arc<Mutex<PythonBridgeState>>>,
    app_handle: AppHandle,
    window: Window,
) -> Result<String, String> {
    println!("=== START_PYTHON_BRIDGE COMMAND CALLED ===");
    start_python_bridge_internal(state, app_handle, window).await
}

// Command to stop the Python bridge
#[tauri::command]
async fn stop_python_bridge(
    state: State<'_, Arc<Mutex<PythonBridgeState>>>,
    window: Window,
) -> Result<String, String> {
    let mut state = state.lock().unwrap();
    
    if !state.is_running {
        return Err("Python bridge is not running".to_string());
    }
    
    if let Some(mut process) = state.process.take() {
        match process.kill() {
            Ok(_) => {
                println!("Stopped Python bridge process");
                state.is_running = false;
                
                // Emit event to frontend using the window object
                let _ = window.emit("python-bridge-status", false);
                
                Ok("Python bridge stopped successfully".to_string())
            },
            Err(e) => {
                // Put the process back
                state.process = Some(process);
                Err(format!("Failed to stop Python bridge: {}", e))
            }
        }
    } else {
        state.is_running = false;
        Ok("Python bridge was not running".to_string())
    }
}

// Helper function to get the Python command
fn get_python_command(app_handle: &AppHandle) -> Result<(String, Option<Vec<String>>), String> {
    // Check if we're in production (bundled) or development mode
    if cfg!(debug_assertions) {
        // In development, use the system Python
        #[cfg(target_os = "windows")]
        {
            Ok(("python".to_string(), Some(vec!["-m".to_string(), "aya.tauri_bridge".to_string()])))
        }
        #[cfg(not(target_os = "windows"))]
        {
            Ok(("python3".to_string(), Some(vec!["-m".to_string(), "aya.tauri_bridge".to_string()])))
        }
    } else {
        // In production, use the bundled executable
        let app_dir = app_handle.path_resolver().app_data_dir().ok_or("Failed to get app directory")?;
        
        #[cfg(target_os = "windows")]
        {
            let bridge_path = app_dir.join("resources").join("aya_bridge.exe");
            Ok((bridge_path.to_string_lossy().to_string(), None))
        }
        #[cfg(target_os = "macos")]
        {
            let bridge_path = app_dir.join("Resources").join("aya_bridge");
            Ok((bridge_path.to_string_lossy().to_string(), None))
        }
        #[cfg(target_os = "linux")]
        {
            let bridge_path = app_dir.join("resources").join("aya_bridge");
            Ok((bridge_path.to_string_lossy().to_string(), None))
        }
        #[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
        {
            Err("Unsupported platform".to_string())
        }
    }
}

// Check if Python bridge is running
#[tauri::command]
async fn is_python_bridge_running(
    state: State<'_, Arc<Mutex<PythonBridgeState>>>,
) -> Result<bool, String> {
    let state = state.lock().unwrap();
    Ok(state.is_running)
}

fn main() {
    println!("=== TAURI APPLICATION STARTING ===");
    
    // Create the application
    tauri::Builder::default()
        .manage(Arc::new(Mutex::new(PythonBridgeState::new())))
        .invoke_handler(tauri::generate_handler![
            start_python_bridge,
            stop_python_bridge,
            is_python_bridge_running,
        ])
        .setup(|app| {
            println!("=== TAURI APPLICATION SETUP ===");
            println!("App data dir: {:?}", app.path_resolver().app_data_dir());
            println!("App config dir: {:?}", app.path_resolver().app_config_dir());
            println!("Debug mode: {}", cfg!(debug_assertions));
            
            // Auto-start Python bridge
            let app_handle = app.handle();
            let window = app.get_window("main").expect("no main window");
            let state = app.state::<Arc<Mutex<PythonBridgeState>>>();
            let state_clone = Arc::clone(&state.inner());
            
            tauri::async_runtime::spawn(async move {
                println!("=== AUTO-STARTING PYTHON BRIDGE ===");
                
                // Call the internal logic directly instead of the command wrapper
                match start_python_bridge_direct(state_clone, app_handle, window).await {
                    Ok(msg) => println!("=== PYTHON BRIDGE AUTO-START SUCCESS: {} ===", msg),
                    Err(err) => println!("=== PYTHON BRIDGE AUTO-START FAILED: {} ===", err),
                }
            });
            
            Ok(())
        })
        .on_window_event(|event| {
            match event.event() {
                WindowEvent::CloseRequested { api, .. } => {
                    // Prevent the window from closing, just hide it
                    api.prevent_close();
                    let window = event.window();
                    let _ = window.hide();
                },
                _ => {}
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
} 