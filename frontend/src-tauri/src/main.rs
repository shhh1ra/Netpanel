#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf};

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct HostProfile {
    id: String,
    name: String,
    host: String,
    port: u16,
    username: String,
    #[serde(default)]
    password: String,
    #[serde(default = "password_auth")]
    auth_type: String,
    #[serde(default)]
    key_path: Option<String>,
}

fn password_auth() -> String {
    "password".to_string()
}

fn hosts_path() -> Result<PathBuf, String> {
    let executable = std::env::current_exe().map_err(|error| error.to_string())?;
    let directory = executable
        .parent()
        .ok_or_else(|| "Cannot determine application directory".to_string())?;
    Ok(directory.join("hosts.json"))
}

#[tauri::command]
fn load_host_profiles() -> Result<Option<Vec<HostProfile>>, String> {
    let path = hosts_path()?;
    if !path.exists() {
        return Ok(None);
    }

    let contents = fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&contents)
        .map(Some)
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn save_host_profiles(profiles: Vec<HostProfile>) -> Result<(), String> {
    let contents = serde_json::to_string_pretty(&profiles).map_err(|error| error.to_string())?;
    fs::write(hosts_path()?, format!("{contents}\n")).map_err(|error| error.to_string())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            load_host_profiles,
            save_host_profiles
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
