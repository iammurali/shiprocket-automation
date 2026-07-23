//! CLI harness: run processing pipelines headlessly for verification.
//! Usage:
//!   extract-test dump <pdf>                  — page texts as JSON
//!   extract-test shiprocket <in> <out> [4x4] — run tab-1 pipeline
//!   extract-test delhivery <in> <out> [4x4]  — run tab-4 pipeline
//!   extract-test st <in> <out>               — run tab-3 pipeline

use shiprocket_label_processor_lib::config::RulesConfig;
use shiprocket_label_processor_lib::pdf::{engine, extract, labelgen};

/// Rules come from the RULES_JSON env var (path to a RulesConfig JSON) when
/// set, else the built-in defaults — lets parity tests and custom-config
/// experiments run headlessly.
fn load_rules() -> RulesConfig {
    std::env::var("RULES_JSON")
        .ok()
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

struct StdoutReporter;
impl engine::Reporter for StdoutReporter {
    fn log(&self, msg: &str) {
        eprintln!("[log] {}", msg);
    }
    fn progress(&self, current: usize, total: usize) {
        eprintln!("[progress] {}/{}", current, total);
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: extract-test <dump|shiprocket|delhivery|st> <in> [out] [4x4]");
        std::process::exit(2);
    }
    let cmd = args[1].as_str();
    match cmd {
        "dump" => {
            let texts = extract::extract_pages_text(&args[2]).expect("extract");
            println!("{}", serde_json::to_string(&texts).unwrap());
        }
        "shiprocket" | "delhivery" => {
            // input may be comma-separated for batch processing
            let inputs: Vec<String> = args[2].split(',').map(|s| s.to_string()).collect();
            let rules = load_rules();
            let out = args.get(3).expect("need output path");
            let is_4x4 = args.get(4).map(|s| s == "4x4").unwrap_or(false);
            let rep = StdoutReporter;
            let stats = if cmd == "shiprocket" {
                engine::process_shiprocket(&rules, &inputs, out, is_4x4, &rep)
            } else {
                engine::process_delhivery(&rules, &inputs, out, &rep)
            }
            .expect("pipeline failed");
            println!("{}", serde_json::to_string(&stats).unwrap());
        }
        "st" => {
            let inputs: Vec<String> = args[2].split(',').map(|s| s.to_string()).collect();
            let rules = load_rules();
            let out = args.get(3).expect("need output path");
            let stats =
                engine::process_st(&rules, &inputs, out, &StdoutReporter).expect("st failed");
            println!("{}", serde_json::to_string(&stats).unwrap());
        }
        "labels" => {
            // labels <orders.json> <out.pdf> [4x4] [logo.png]
            let orders: Vec<labelgen::QueueOrder> =
                serde_json::from_str(&std::fs::read_to_string(&args[2]).expect("read orders"))
                    .expect("parse orders");
            let out = args.get(3).expect("need output path");
            let is_4x4 = args.get(4).map(|s| s == "4x4").unwrap_or(false);
            let logo = args
                .get(5)
                .and_then(|p| labelgen::load_logo(std::path::Path::new(p)));
            let rules = load_rules();
            labelgen::generate_labels(
                &rules.courier,
                &orders,
                is_4x4,
                logo.as_ref(),
                std::path::Path::new(out),
            )
            .expect("labelgen failed");
            println!("wrote {}", out);
        }
        other => {
            eprintln!("unknown subcommand: {}", other);
            std::process::exit(2);
        }
    }
}
