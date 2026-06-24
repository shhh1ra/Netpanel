#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf};

#[derive(Clone, Debug, Deserialize, Serialize)]
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

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct StoredHostProfile {
    id: String,
    name: String,
    host: String,
    port: u16,
    username: String,
    #[serde(default, skip_serializing)]
    password: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    password_protected: Option<String>,
    #[serde(default = "password_auth")]
    auth_type: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
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
    let stored: Vec<StoredHostProfile> =
        serde_json::from_str(&contents).map_err(|error| error.to_string())?;
    let mut migrated_plaintext = false;
    let mut profiles = Vec::with_capacity(stored.len());

    for profile in stored {
        let password = if let Some(protected) = profile.password_protected {
            unprotect_password(&protected)?
        } else {
            let plaintext = profile.password.unwrap_or_default();
            migrated_plaintext |= !plaintext.is_empty();
            plaintext
        };
        profiles.push(HostProfile {
            id: profile.id,
            name: profile.name,
            host: profile.host,
            port: profile.port,
            username: profile.username,
            password,
            auth_type: profile.auth_type,
            key_path: profile.key_path,
        });
    }

    if migrated_plaintext {
        write_host_profiles(&profiles)?;
    }
    Ok(Some(profiles))
}

#[tauri::command]
fn save_host_profiles(profiles: Vec<HostProfile>) -> Result<(), String> {
    write_host_profiles(&profiles)
}

fn write_host_profiles(profiles: &[HostProfile]) -> Result<(), String> {
    let stored = profiles
        .iter()
        .map(|profile| {
            let password_protected = if profile.password.is_empty() {
                None
            } else {
                Some(protect_password(&profile.password)?)
            };
            Ok(StoredHostProfile {
                id: profile.id.clone(),
                name: profile.name.clone(),
                host: profile.host.clone(),
                port: profile.port,
                username: profile.username.clone(),
                password: None,
                password_protected,
                auth_type: profile.auth_type.clone(),
                key_path: profile.key_path.clone(),
            })
        })
        .collect::<Result<Vec<_>, String>>()?;
    let contents = serde_json::to_string_pretty(&stored).map_err(|error| error.to_string())?;
    fs::write(hosts_path()?, format!("{contents}\n")).map_err(|error| error.to_string())
}

#[cfg(windows)]
fn protect_password(password: &str) -> Result<String, String> {
    use base64::{engine::general_purpose::STANDARD, Engine};
    use std::{ptr, slice};
    use windows::{
        core::{Error, PCWSTR},
        Win32::{
            Security::Cryptography::{
                CryptProtectData, CRYPTOAPI_BLOB, CRYPTPROTECT_UI_FORBIDDEN,
            },
            System::Memory::LocalFree,
        },
    };

    let bytes = password.as_bytes();
    let input = CRYPTOAPI_BLOB {
        cbData: bytes.len() as u32,
        pbData: bytes.as_ptr() as *mut u8,
    };
    let mut output = CRYPTOAPI_BLOB {
        cbData: 0,
        pbData: ptr::null_mut(),
    };
    let success = unsafe {
        CryptProtectData(
            &input,
            PCWSTR::null(),
            ptr::null(),
            ptr::null_mut(),
            ptr::null(),
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut output,
        )
    };
    if !success.as_bool() {
        return Err(Error::from_win32().to_string());
    }

    let protected = unsafe { slice::from_raw_parts(output.pbData, output.cbData as usize) };
    let encoded = STANDARD.encode(protected);
    unsafe {
        LocalFree(output.pbData as isize);
    }
    Ok(encoded)
}

#[cfg(windows)]
fn unprotect_password(encoded: &str) -> Result<String, String> {
    use base64::{engine::general_purpose::STANDARD, Engine};
    use std::{ptr, slice};
    use windows::{
        core::Error,
        Win32::{
            Security::Cryptography::{
                CryptUnprotectData, CRYPTOAPI_BLOB, CRYPTPROTECT_UI_FORBIDDEN,
            },
            System::Memory::LocalFree,
        },
    };

    let mut encrypted = STANDARD.decode(encoded).map_err(|error| error.to_string())?;
    let input = CRYPTOAPI_BLOB {
        cbData: encrypted.len() as u32,
        pbData: encrypted.as_mut_ptr(),
    };
    let mut output = CRYPTOAPI_BLOB {
        cbData: 0,
        pbData: ptr::null_mut(),
    };
    let success = unsafe {
        CryptUnprotectData(
            &input,
            ptr::null_mut(),
            ptr::null(),
            ptr::null_mut(),
            ptr::null(),
            CRYPTPROTECT_UI_FORBIDDEN,
            &mut output,
        )
    };
    if !success.as_bool() {
        return Err(Error::from_win32().to_string());
    }

    let decrypted = unsafe { slice::from_raw_parts(output.pbData, output.cbData as usize) }.to_vec();
    unsafe {
        LocalFree(output.pbData as isize);
    }
    String::from_utf8(decrypted).map_err(|error| error.to_string())
}

#[cfg(not(windows))]
fn protect_password(_password: &str) -> Result<String, String> {
    Err("Protected password storage is currently available only on Windows".to_string())
}

#[cfg(not(windows))]
fn unprotect_password(_encoded: &str) -> Result<String, String> {
    Err("Protected password storage is currently available only on Windows".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(windows)]
    #[test]
    fn dpapi_password_round_trip() {
        let protected = protect_password("Cisco-test-password").expect("protect password");
        assert_ne!(protected, "Cisco-test-password");
        assert_eq!(
            unprotect_password(&protected).expect("unprotect password"),
            "Cisco-test-password"
        );
    }

    #[cfg(windows)]
    #[test]
    fn stored_profile_omits_plaintext_password() {
        let protected = protect_password("secret").expect("protect password");
        let stored = StoredHostProfile {
            id: "1".to_string(),
            name: "SW1".to_string(),
            host: "192.0.2.1".to_string(),
            port: 22,
            username: "admin".to_string(),
            password: None,
            password_protected: Some(protected),
            auth_type: "password".to_string(),
            key_path: None,
        };
        let json = serde_json::to_string(&stored).expect("serialize profile");
        let value: serde_json::Value = serde_json::from_str(&json).expect("parse stored profile");
        assert!(value.get("password").is_none());
        assert!(!json.contains("secret"));
        assert!(value.get("passwordProtected").is_some());
    }
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
