//! Pure label-processing logic ported from pdf_gui.py, parameterized by the
//! user-editable RulesConfig. Operates on extracted page text; no PDF I/O.

use crate::config::RulesConfig;
use regex::Regex;
use std::collections::BTreeMap;
use std::sync::LazyLock;

static SKU_PATTERN: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(?i)SKU:\s*([\w\-]+)").unwrap());
static QTY_PATTERN: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(\d+)").unwrap());
static WS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\s+").unwrap());
static ONLY_NUM: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^\d+$").unwrap());
static TRAILING_NUM: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(\d+)\s*$").unwrap());

fn first_int(s: &str) -> Option<i64> {
    QTY_PATTERN
        .captures(s)
        .and_then(|c| c.get(1))
        .and_then(|m| m.as_str().parse::<i64>().ok())
}

pub fn sku_product_name<'a>(rules: &'a RulesConfig, sku: &str) -> &'a str {
    rules
        .sku_lookup(sku)
        .map(|p| p.name.as_str())
        .unwrap_or("Unknown Product")
}

/// Port of extract_skus_from_page. `lines` are text.splitlines() (unstripped).
pub fn extract_skus_from_page(rules: &RulesConfig, lines: &[&str]) -> Vec<(String, String)> {
    let mut sku_labels = Vec::new();
    let mut i = 0usize;
    let n = lines.len();

    let make_label = |sku: &str, qty: i64| -> String {
        let product_name = sku_product_name(rules, sku);
        if qty > 1 {
            format!("→ {}x{}", product_name, qty)
        } else {
            format!("→ {}", product_name)
        }
    };

    while i < n {
        let line = lines[i];
        let sku_match = SKU_PATTERN.captures(line);

        if let Some(caps) = sku_match.as_ref().filter(|c| !c[1].ends_with('-')) {
            let sku = caps[1].to_string();
            let mut qty: i64 = 1;
            if i + 1 < n {
                if let Some(q) = first_int(lines[i + 1]) {
                    qty = q;
                }
            }
            let label_text = make_label(&sku, qty);
            sku_labels.push((sku, label_text));
            i += 2;
        } else if line.contains("SKU:") && i + 1 < n {
            let sku_prefix = line.replace("SKU:", "").trim().to_string();
            let sku_suffix = lines[i + 1].trim().to_string();

            let sku_full = if !sku_prefix.is_empty()
                && !sku_suffix.is_empty()
                && !sku_prefix.ends_with('-')
                && !sku_suffix.starts_with('-')
            {
                format!("{}-{}", sku_prefix, sku_suffix)
            } else {
                format!("{}{}", sku_prefix, sku_suffix)
            };

            let sku = sku_full.replace(' ', "");
            let mut qty: i64 = 1;
            if i + 2 < n {
                if let Some(q) = first_int(lines[i + 2])
                {
                    qty = q;
                }
            }
            let label_text = make_label(&sku, qty);
            sku_labels.push((sku, label_text));
            i += 3;
        } else {
            i += 1;
        }
    }

    sku_labels
}

/// Counts keyed by "1"/"2"/"3"/"more" like the Python dicts.
pub type Counts = BTreeMap<String, i64>;
/// product name -> qty-bucket counts
pub type ProductCounts = BTreeMap<String, Counts>;

pub fn label_qty(label_text: &str) -> i64 {
    // Python: int(label_text.split("x")[1]) when "x" in label
    if let Some(pos) = label_text.find('x') {
        let rest = &label_text[pos + 1..];
        let end = rest
            .find(|c: char| !c.is_ascii_digit())
            .unwrap_or(rest.len());
        rest[..end].parse::<i64>().unwrap_or(1)
    } else {
        1
    }
}

/// Count per tracked product (generalization of count_products which only
/// tracked OIL and Potli).
pub fn count_products(rules: &RulesConfig, sku_labels: &[(String, String)]) -> ProductCounts {
    let mut counts = ProductCounts::new();
    for (sku, label_text) in sku_labels {
        if let Some(p) = rules.sku_lookup(sku).filter(|p| p.track_in_stats) {
            let qty = label_qty(label_text);
            let bucket = if qty <= 3 {
                qty.to_string()
            } else {
                "more".to_string()
            };
            *counts
                .entry(p.name.clone())
                .or_default()
                .entry(bucket)
                .or_insert(0) += 1;
        }
    }
    counts
}

pub fn merge_counts(total: &mut ProductCounts, page: ProductCounts) {
    for (product, buckets) in page {
        let t = total.entry(product).or_default();
        for (k, v) in buckets {
            *t.entry(k).or_insert(0) += v;
        }
    }
}

/// Port of group_pages_optimized (group order derived from the rules).
/// marked_pages: (page_index, label_text); returns (page_index, Option<label>).
/// `file_boundaries` holds the global index of each input file's first page so
/// the unmarked+marked pairing never spans two different source PDFs.
pub fn group_pages(
    rules: &RulesConfig,
    marked_pages: &[(usize, String)],
    unmarked_pages: &[usize],
    skipped_pages: &std::collections::HashSet<usize>,
    file_boundaries: &std::collections::HashSet<usize>,
) -> Vec<(usize, Option<String>)> {
    let marked_dict: BTreeMap<usize, &String> =
        marked_pages.iter().map(|(i, l)| (*i, l)).collect();

    let mut grouped_pairs: Vec<(usize, usize)> = Vec::new();
    let mut used_pages: std::collections::HashSet<usize> = std::collections::HashSet::new();

    for &page in unmarked_pages {
        let next_page = page + 1;
        if marked_dict.contains_key(&next_page)
            && !skipped_pages.contains(&page)
            && !skipped_pages.contains(&next_page)
            && !file_boundaries.contains(&next_page)
        {
            grouped_pairs.push((page, next_page));
            used_pages.insert(page);
            used_pages.insert(next_page);
        }
    }

    let remaining_marked: Vec<(usize, &String)> = marked_pages
        .iter()
        .filter(|(i, _)| !used_pages.contains(i))
        .map(|(i, l)| (*i, l))
        .collect();
    let remaining_unmarked: Vec<usize> = unmarked_pages
        .iter()
        .filter(|i| !used_pages.contains(i))
        .cloned()
        .collect();

    let mut single_product_pages: Vec<(usize, &String)> = Vec::new();
    let mut mixed_product_pages: Vec<(usize, &String)> = Vec::new();

    for (i, label_text) in &remaining_marked {
        if label_text.contains(" | ") {
            mixed_product_pages.push((*i, label_text));
        } else {
            single_product_pages.push((*i, label_text));
        }
    }

    // Insertion-ordered grouping (python dict semantics), key = normalized label
    let mut group_keys: Vec<String> = Vec::new();
    let mut page_groups: std::collections::HashMap<String, Vec<(usize, &String)>> =
        std::collections::HashMap::new();
    for (i, label_text) in &single_product_pages {
        let normalized = label_text.replace("→ ", "").replace(' ', "").to_uppercase();
        if !page_groups.contains_key(&normalized) {
            group_keys.push(normalized.clone());
        }
        page_groups.entry(normalized).or_default().push((*i, label_text));
    }

    let mut final_order: Vec<(usize, Option<String>)> = Vec::new();
    final_order.extend(remaining_unmarked.iter().map(|&i| (i, None)));

    let mut remaining_keys: Vec<String> = group_keys.clone();
    for group in rules.group_order() {
        let mut sorted_keys: Vec<String> = remaining_keys.clone();
        sorted_keys.sort();
        let mut removed: Vec<String> = Vec::new();
        for key in &sorted_keys {
            if key.starts_with(&group) {
                if let Some(pages) = page_groups.get(key) {
                    final_order
                        .extend(pages.iter().map(|(i, l)| (*i, Some((*l).clone()))));
                }
                removed.push(key.clone());
            }
        }
        remaining_keys.retain(|k| !removed.contains(k));
    }

    let mut leftover: Vec<String> = remaining_keys;
    leftover.sort();
    for key in leftover {
        if let Some(pages) = page_groups.get(&key) {
            final_order.extend(pages.iter().map(|(i, l)| (*i, Some((*l).clone()))));
        }
    }

    for (no_sku, sku_page) in grouped_pairs {
        final_order.push((no_sku, None));
        final_order.push((sku_page, Some((*marked_dict[&sku_page]).clone())));
    }

    final_order.extend(
        mixed_product_pages
            .iter()
            .map(|(i, l)| (*i, Some((*l).clone()))),
    );

    final_order
}

// ---------- keyword-based product matching (ST + Delhivery) ----------

/// (family_code, qty, product_name)
pub type StProduct = (i64, i64, String);

/// First product (in match-priority order) with a keyword contained in `line`.
/// Returns (product_index, canonical_name).
fn match_product<'a>(rules: &'a RulesConfig, line: &str) -> Option<(usize, &'a str)> {
    let lower = line.to_lowercase();
    for idx in rules.match_order() {
        let p = &rules.products[idx];
        if p.keywords
            .iter()
            .any(|k| !k.trim().is_empty() && lower.contains(&k.trim().to_lowercase()))
        {
            return Some((idx, p.canonical_name.as_str()));
        }
    }
    None
}

/// Port of extract_st_products with configurable products.
pub fn extract_st_products(rules: &RulesConfig, text: &str) -> Vec<StProduct> {
    let mut seen: std::collections::HashSet<StProduct> = std::collections::HashSet::new();
    let mut products: Vec<StProduct> = Vec::new();
    let line_filter = rules.st.line_filter.to_lowercase();

    let lines: Vec<&str> = text.split('\n').collect();

    for (i, line) in lines.iter().enumerate() {
        let line_stripped = line.trim();
        if line_stripped.is_empty() {
            continue;
        }
        if !line_filter.is_empty() && !line.to_lowercase().contains(&line_filter) {
            continue;
        }

        if let Some((idx, canonical)) = match_product(rules, line) {
            let mut qty: i64 = 1;

            // Strategy 1: pipe-separated table
            if line.contains('|') {
                let parts: Vec<&str> = line.split('|').collect();
                if parts.len() >= 2 {
                    if let Some(q) = first_int(parts.last().unwrap()) {
                        qty = q;
                    }
                }
            }
            // Strategy 2: qty alone on next line
            else if i + 1 < lines.len() {
                let next_line = lines[i + 1].trim();
                if ONLY_NUM.is_match(next_line) {
                    qty = next_line.parse().unwrap_or(1);
                }
            }

            // Strategy 3: digit at end of current line
            if qty == 1 {
                if let Some(caps) = TRAILING_NUM.captures(line) {
                    let qty_str = caps[1].to_string();
                    let last_word = line_stripped.split_whitespace().last().unwrap_or("");
                    if !last_word.contains(&qty_str) || !line_stripped.contains("100") {
                        qty = qty_str.parse().unwrap_or(1);
                    }
                }
            }

            let key = (rules.family_code(idx), qty, canonical.to_string());
            if !seen.contains(&key) {
                seen.insert(key.clone());
                products.push(key);
            }
        }
    }
    products
}

/// Port of extract_delhivery_products with configurable products/rules.
pub fn extract_delhivery_products(rules: &RulesConfig, text: &str) -> Vec<StProduct> {
    let lines: Vec<&str> = text.lines().collect();
    let mut seen: std::collections::HashSet<StProduct> = std::collections::HashSet::new();
    let mut products: Vec<StProduct> = Vec::new();
    let dd = &rules.delhivery;

    let qty_regexes: Vec<Regex> = dd
        .qty_patterns
        .iter()
        .filter_map(|p| Regex::new(p).ok())
        .collect();

    let extract_qty = |index: usize| -> i64 {
        for offset in 0..dd.qty_scan_lines {
            let scan = index + offset;
            if scan >= lines.len() {
                break;
            }
            let candidate = lines[scan].trim();
            if candidate.is_empty() {
                continue;
            }
            for pat in &qty_regexes {
                if let Some(c) = pat.captures(candidate) {
                    if let Some(q) = c.get(1).and_then(|m| m.as_str().parse::<i64>().ok()) {
                        return q;
                    }
                }
            }
        }
        1
    };

    let line_filter = dd.line_filter.to_lowercase();

    // "Unknown" family: keeps the raw line, family code after all products
    let unknown_code = rules.products.len() as i64;

    for (i, line) in lines.iter().enumerate() {
        let line_stripped = line.trim();
        if line_stripped.is_empty() {
            continue;
        }
        let normalized_line = WS.replace_all(line_stripped, " ").to_lowercase();
        if dd
            .skip_contains
            .iter()
            .any(|s| !s.is_empty() && normalized_line.contains(&s.to_lowercase()))
        {
            continue;
        }
        if dd
            .skip_prefixes
            .iter()
            .any(|s| !s.is_empty() && normalized_line.starts_with(&s.to_lowercase()))
        {
            continue;
        }
        if !line_filter.is_empty() && !normalized_line.starts_with(&line_filter) {
            continue;
        }

        let (code, name) = match match_product(rules, line_stripped) {
            Some((idx, canonical)) => (rules.family_code(idx), canonical.to_string()),
            None => (unknown_code, line_stripped.to_string()),
        };
        let qty = extract_qty(i);
        let key = (code, qty, name);
        if !seen.contains(&key) {
            seen.insert(key.clone());
            products.push(key);
        }
    }

    // Fallback: derive from SKU labels when no product line matched
    if products.is_empty() {
        let sku_labels = extract_skus_from_page(rules, &lines);
        for (_sku, label_text) in sku_labels {
            let qty = if label_text.contains('x') {
                label_qty(&label_text)
            } else {
                1
            };
            let product_name = label_text.replace('→', "").trim().to_string();
            let (code, name) = match match_product(rules, &product_name) {
                Some((idx, canonical)) => (rules.family_code(idx), canonical.to_string()),
                None => (unknown_code, product_name),
            };
            let key = (code, qty, name);
            if !seen.contains(&key) {
                seen.insert(key.clone());
                products.push(key);
            }
        }
    }

    products
}

/// Compact marker like "OIL", "OILX2" (port of format_product_label).
pub fn format_product_label(stamp_label: &str, qty: i64) -> String {
    let family = stamp_label.trim().to_uppercase();
    if qty > 1 {
        format!("{}X{}", family, qty)
    } else {
        family
    }
}

/// Stamp label for a family code (product index), "OTHER" for unknown.
pub fn stamp_label_for_code<'a>(rules: &'a RulesConfig, code: i64) -> &'a str {
    rules
        .products
        .get(code as usize)
        .map(|p| p.stamp_label.as_str())
        .unwrap_or("OTHER")
}

/// Display name for a family code, "Other" for unknown.
pub fn name_for_code<'a>(rules: &'a RulesConfig, code: i64) -> &'a str {
    rules
        .products
        .get(code as usize)
        .map(|p| p.name.as_str())
        .unwrap_or("Other")
}

/// Sort key port of sort_st_marked_pages (also used by Delhivery).
pub fn sort_st_marked_pages(marked_pages: &mut Vec<(usize, Vec<StProduct>)>) {
    fn sort_key(products: &[StProduct]) -> (i64, Vec<(i64, i64)>, String) {
        if products.is_empty() {
            return (2, Vec::new(), String::new());
        }
        let is_multi = if products.len() > 1 { 1 } else { 0 };
        let mut sorted_products = products.to_vec();
        sorted_products.sort_by(|a, b| (a.0, a.1).cmp(&(b.0, b.1)));
        let pairs: Vec<(i64, i64)> = sorted_products.iter().map(|p| (p.0, p.1)).collect();
        let primary = sorted_products
            .first()
            .map(|p| p.2.clone())
            .unwrap_or_default();
        (is_multi, pairs, primary)
    }

    marked_pages.sort_by(|a, b| sort_key(&a.1).cmp(&sort_key(&b.1)));
}
