use serde::{Deserialize, Serialize};
use std::path::PathBuf;

// ---------------- Rules (label-processing behavior) ----------------
//
// Everything product- or format-specific lives here so new products or label
// changes are a settings edit, not a code change. Defaults reproduce the
// behavior of pdf_gui.py (commit c8eceec).

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ProductRule {
    /// Display/family name used in tab-1 stamps and stats ("OIL", "Potli", …)
    pub name: String,
    /// Compact marker for ST/Delhivery stamps and grouping ("OIL", "POTLI", …)
    pub stamp_label: String,
    /// Canonical product name recorded for ST/Delhivery pages
    pub canonical_name: String,
    /// Case-insensitive keywords; a line matches this product when it contains
    /// ANY of them. Products are evaluated in list order — first match wins.
    pub keywords: Vec<String>,
    /// SKU codes that map to this product (tab 1)
    pub skus: Vec<String>,
    /// Include this product in the statistics panel
    pub track_in_stats: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct ShiprocketTabRules {
    pub stamp_x: f64,
    pub stamp_y: f64,
    pub stamp_size: f64,
    pub stamp_color: String, // hex like "#ff0000"
    pub crop_mm: f64,
    pub crop_skip_last_page: bool,
    /// Max quantity variant per product used to build the grouping order
    /// (e.g. 4 → OIL, OILX2, OILX3, OILX4)
    pub group_max_qty: i64,
}

impl Default for ShiprocketTabRules {
    fn default() -> Self {
        Self {
            stamp_x: 5.0,
            stamp_y: 250.0,
            stamp_size: 12.0,
            stamp_color: "#ff0000".into(),
            crop_mm: 50.0,
            crop_skip_last_page: true,
            group_max_qty: 4,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct StTabRules {
    /// A line must contain this (case-insensitive) before product matching
    pub line_filter: String,
    pub phone_pattern: String,
    pub phone_note: String,
}

impl Default for StTabRules {
    fn default() -> Self {
        Self {
            line_filter: "tulir naturals".into(),
            phone_pattern: r"^PH(?:ONE)?\s*:\s*\+?\d".into(),
            phone_note: "<-- CALL THIS NUMBER".into(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct DelhiveryTabRules {
    /// Normalized line must START with this (case-insensitive)
    pub line_filter: String,
    /// Lines containing any of these are skipped (table headers etc.)
    pub skip_contains: Vec<String>,
    /// Lines starting with any of these are skipped
    pub skip_prefixes: Vec<String>,
    /// Regexes tried in order (first capture group = qty), scanned over the
    /// product line and the next few lines
    pub qty_patterns: Vec<String>,
    pub qty_scan_lines: usize,
    pub stamp_x: f64,
    /// Distance of the stamp baseline from the page bottom (points)
    pub stamp_from_bottom: f64,
    pub stamp_size: f64,
    pub stamp_color: String,
    pub phone_pattern: String,
    pub phone_note: String,
}

impl Default for DelhiveryTabRules {
    fn default() -> Self {
        Self {
            line_filter: "tulir naturals".into(),
            skip_contains: vec!["product name".into(), "qty".into()],
            skip_prefixes: vec!["seller:".into()],
            qty_patterns: vec![
                r"(?i)qty\s*[:\-]?\s*(\d+)".into(),
                r"(?i)x\s*(\d+)".into(),
                r"(?i)(\d+)\s*pcs?".into(),
                r"^(\d+)$".into(),
            ],
            qty_scan_lines: 5,
            stamp_x: 20.0,
            stamp_from_bottom: 72.0,
            stamp_size: 12.0,
            stamp_color: "#ff0000".into(),
            phone_pattern: r"^(PH|PHONE|MOBILE)\s*[:\-]?\s*\+?\d".into(),
            phone_note: "<-- CALL THIS NUMBER".into(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct CourierRules {
    pub brand_name: String,
    pub title_color: String,
    pub from_address: String,
    pub from_address_4x4: String,
}

impl Default for CourierRules {
    fn default() -> Self {
        Self {
            brand_name: "Tulir Naturals".into(),
            title_color: "#1a591a".into(),
            from_address: "From:\nTulir Naturals\nEdaikazhinadu, kadapakkam\ncheyyur Taluk, Chengalpat district\n603304\nPh: 8778469045".into(),
            from_address_4x4: "From: Tulir Naturals\nEdaikazhinadu, kadapakkam\ncheyyur Taluk, Chengalpat district - 603304\nPh: 8778469045".into(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct RulesConfig {
    pub products: Vec<ProductRule>,
    pub shiprocket: ShiprocketTabRules,
    pub st: StTabRules,
    pub delhivery: DelhiveryTabRules,
    pub courier: CourierRules,
}

impl Default for RulesConfig {
    fn default() -> Self {
        Self {
            // Order matters: first keyword match wins (Potli/Varico before the
            // broader Oil rule), and list order defines sort priority.
            products: vec![
                ProductRule {
                    name: "OIL".into(),
                    stamp_label: "OIL".into(),
                    canonical_name: "Tulir Naturals Oil 100ml".into(),
                    keywords: vec!["oil".into(), "100ml".into()],
                    skus: vec!["TN0001".into(), "TS-NLT5-CZ47".into()],
                    track_in_stats: true,
                },
                ProductRule {
                    name: "Potli".into(),
                    stamp_label: "POTLI".into(),
                    canonical_name: "Tulir Naturals - Massager Potli".into(),
                    keywords: vec!["potli".into()],
                    skus: vec!["TN0002".into(), "84-HNM4-WOND".into()],
                    track_in_stats: true,
                },
                ProductRule {
                    name: "Varico".into(),
                    stamp_label: "VARICO".into(),
                    canonical_name: "Tulir Naturals - Varico Oil".into(),
                    keywords: vec!["varico".into()],
                    skus: vec!["43522344878158".into(), "TN0005".into()],
                    track_in_stats: false,
                },
                ProductRule {
                    name: "Rollon".into(),
                    stamp_label: "ROLLON".into(),
                    canonical_name: "Tulir Naturals - Rollon".into(),
                    keywords: vec!["rollon".into(), "roll on".into()],
                    skus: vec!["TN003".into()],
                    track_in_stats: false,
                },
            ],
            shiprocket: ShiprocketTabRules::default(),
            st: StTabRules::default(),
            delhivery: DelhiveryTabRules::default(),
            courier: CourierRules::default(),
        }
    }
}

impl RulesConfig {
    /// Matching priority order: Potli/Varico/Rollon before the broad Oil rule.
    /// (Oil keywords like "oil" also appear in "Varico Oil".)
    pub fn match_order(&self) -> Vec<usize> {
        let mut idx: Vec<usize> = (0..self.products.len()).collect();
        // products whose keywords are a subset of another product's text keep
        // list order; the broad-first problem is solved by putting products
        // with MORE specific keywords first: evaluate non-Oil-like products
        // in order, then the rest. Simplest robust rule: evaluate in list
        // order but skip products whose keyword set matches a later product's
        // canonical name — instead, we simply evaluate products in reverse
        // specificity: those whose canonical_name is NOT matched by any other
        // product's keywords first.
        idx.sort_by_key(|&i| {
            let p = &self.products[i];
            let broad = self
                .products
                .iter()
                .enumerate()
                .any(|(j, other)| {
                    j != i
                        && p.keywords.iter().any(|k| {
                            other.canonical_name.to_lowercase().contains(&k.to_lowercase())
                        })
                });
            (broad, i)
        });
        idx
    }

    /// family code for sorting = index in the products list
    pub fn family_code(&self, product_index: usize) -> i64 {
        product_index as i64
    }

    pub fn sku_lookup(&self, sku: &str) -> Option<&ProductRule> {
        self.products
            .iter()
            .find(|p| p.skus.iter().any(|s| s == sku))
    }

    /// Grouping order for tab 1: for each product in list order emit
    /// LABEL, LABELX2 … LABELX{group_max_qty}
    pub fn group_order(&self) -> Vec<String> {
        let mut out = Vec::new();
        for p in &self.products {
            let base = p.stamp_label.to_uppercase();
            out.push(base.clone());
            for q in 2..=self.shiprocket.group_max_qty {
                out.push(format!("{}X{}", base, q));
            }
        }
        out
    }
}

pub fn parse_hex_color(s: &str) -> (f64, f64, f64) {
    let h = s.trim().trim_start_matches('#');
    if h.len() == 6 {
        if let (Ok(r), Ok(g), Ok(b)) = (
            u8::from_str_radix(&h[0..2], 16),
            u8::from_str_radix(&h[2..4], 16),
            u8::from_str_radix(&h[4..6], 16),
        ) {
            return (r as f64 / 255.0, g as f64 / 255.0, b as f64 / 255.0);
        }
    }
    (1.0, 0.0, 0.0)
}

// ---------------- App config (credentials + rules) ----------------

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct AppConfig {
    #[serde(default)]
    pub email: String,
    #[serde(default)]
    pub password: String,
    #[serde(default)]
    pub token: String,
    #[serde(default)]
    pub shopify_url: String,
    #[serde(default)]
    pub shopify_token: String,
    #[serde(default)]
    pub rules: RulesConfig,
}

fn config_path() -> PathBuf {
    let dir = dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("shiprocket-label-processor");
    let _ = std::fs::create_dir_all(&dir);
    dir.join("config.json")
}

pub fn load() -> AppConfig {
    std::fs::read_to_string(config_path())
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

pub fn save(config: &AppConfig) -> Result<(), String> {
    let s = serde_json::to_string_pretty(config).map_err(|e| e.to_string())?;
    std::fs::write(config_path(), s).map_err(|e| e.to_string())
}
