pub mod api;
pub mod config;
pub mod pdf;

use pdf::engine::{self, ProcessStats, Reporter};
use pdf::labelgen::{self, QueueOrder};
use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager};

#[derive(Clone, Serialize)]
struct LogEvent {
    tab: String,
    message: String,
}

#[derive(Clone, Serialize)]
struct ProgressEvent {
    tab: String,
    current: usize,
    total: usize,
}

struct EventReporter {
    app: AppHandle,
    tab: String,
}

impl Reporter for EventReporter {
    fn log(&self, msg: &str) {
        let _ = self.app.emit(
            "proc-log",
            LogEvent {
                tab: self.tab.clone(),
                message: msg.to_string(),
            },
        );
    }
    fn progress(&self, current: usize, total: usize) {
        let _ = self.app.emit(
            "proc-progress",
            ProgressEvent {
                tab: self.tab.clone(),
                current,
                total,
            },
        );
    }
}

#[tauri::command]
async fn process_shiprocket(
    app: AppHandle,
    inputs: Vec<String>,
    output: String,
    is4x4: bool,
) -> Result<ProcessStats, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let rep = EventReporter {
            app: app.clone(),
            tab: "shiprocket".into(),
        };
        let rules = config::load().rules;
        engine::process_shiprocket(&rules, &inputs, &output, is4x4, &rep)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn process_delhivery(
    app: AppHandle,
    inputs: Vec<String>,
    output: String,
) -> Result<ProcessStats, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let rep = EventReporter {
            app: app.clone(),
            tab: "delhivery".into(),
        };
        let rules = config::load().rules;
        engine::process_delhivery(&rules, &inputs, &output, &rep)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn process_st(
    app: AppHandle,
    inputs: Vec<String>,
    output: String,
) -> Result<ProcessStats, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let rep = EventReporter {
            app: app.clone(),
            tab: "st".into(),
        };
        let rules = config::load().rules;
        engine::process_st(&rules, &inputs, &output, &rep)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn generate_labels(
    app: AppHandle,
    orders: Vec<QueueOrder>,
    is4x4: bool,
) -> Result<String, String> {
    tauri::async_runtime::spawn_blocking(move || {
        if orders.is_empty() {
            return Err("No orders to process.".to_string());
        }
        // resolve bundled logo
        let logo = app
            .path()
            .resolve("assets/Logo.png", tauri::path::BaseDirectory::Resource)
            .ok()
            .filter(|p| p.exists())
            .or_else(|| {
                // dev fallback: repo root logo
                let dev = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("assets/Logo.png");
                dev.exists().then_some(dev)
            })
            .and_then(|p| labelgen::load_logo(&p));

        let today = chrono::Local::now().format("%Y-%m-%d").to_string();
        let unique: u32 = 10000 + (rand::random::<u32>() % 90000);
        let filename = format!("ManualLabel-{}-{}.pdf", today, unique);
        let downloads = dirs::download_dir()
            .unwrap_or_else(|| std::path::PathBuf::from("."));
        let full_path = downloads.join(filename);

        let rules = config::load().rules;
        labelgen::generate_labels(&rules.courier, &orders, is4x4, logo.as_ref(), &full_path)?;
        Ok(full_path.to_string_lossy().to_string())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn fetch_order(search_key: String, search_type: String) -> Result<api::OrderDetails, String> {
    api::fetch_order(&search_key, &search_type).await
}

#[tauri::command]
async fn update_shopify(order_ids: Vec<String>) -> Result<api::ShopifyReport, String> {
    api::update_shopify_notes(order_ids).await
}

/// Port of get_default_output_dir: ~/Documents/Shiprocket Label Processor/<tab>/
#[tauri::command]
fn default_output_dir(tab_name: String) -> Result<String, String> {
    let docs = dirs::document_dir().ok_or("No Documents directory")?;
    let dir = docs.join("Shiprocket Label Processor").join(tab_name);
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.to_string_lossy().to_string())
}

#[tauri::command]
fn save_text_file(path: String, content: String) -> Result<(), String> {
    std::fs::write(&path, content).map_err(|e| e.to_string())
}

#[tauri::command]
fn get_config() -> config::AppConfig {
    config::load()
}

/// Built-in default rules, for the "Reset to defaults" button.
#[tauri::command]
fn get_default_rules() -> config::RulesConfig {
    config::RulesConfig::default()
}

#[tauri::command]
fn save_config(cfg: config::AppConfig) -> Result<(), String> {
    // keep existing token when saving settings from the UI
    let mut merged = cfg;
    if merged.token.is_empty() {
        merged.token = config::load().token;
    }
    config::save(&merged)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            process_shiprocket,
            process_delhivery,
            process_st,
            generate_labels,
            fetch_order,
            update_shopify,
            default_output_dir,
            save_text_file,
            get_config,
            get_default_rules,
            save_config
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
