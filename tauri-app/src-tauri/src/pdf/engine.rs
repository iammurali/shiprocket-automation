//! Processing pipelines for the three PDF tabs, matching the current
//! pdf_gui.py behavior (commit c8eceec) with user-configurable rules.

use super::extract;
use super::logic;
use super::write::{self, Annot, Font, PageSpec};
use crate::config::{parse_hex_color, RulesConfig};
use mupdf::Document as MuDocument;
use regex::Regex;
use serde::Serialize;
use std::collections::HashSet;

const MM_TO_PT: f64 = 72.0 / 25.4;
const BLACK: (f64, f64, f64) = (0.0, 0.0, 0.0);

#[derive(Debug, Clone, Serialize, Default)]
pub struct ProcessStats {
    pub total_pages: usize,
    pub marked: usize,
    pub unmarked: usize,
    /// product name -> qty-bucket ("1"/"2"/"3"/"more") -> count
    pub counts: logic::ProductCounts,
}

pub trait Reporter: Send {
    fn log(&self, msg: &str);
    fn progress(&self, current: usize, total: usize);
}

/// Pages of every input concatenated into one global sequence.
struct BatchInput {
    /// page text, global order
    texts: Vec<String>,
    /// global index -> (file index, page index within that file)
    source: Vec<(usize, usize)>,
    /// global index of each file's first page
    boundaries: HashSet<usize>,
}

fn load_batch(inputs: &[String], rep: &dyn Reporter) -> Result<BatchInput, String> {
    if inputs.is_empty() {
        return Err("Please select at least one input PDF file.".into());
    }
    let mut texts = Vec::new();
    let mut source = Vec::new();
    let mut boundaries = HashSet::new();
    for (fi, path) in inputs.iter().enumerate() {
        boundaries.insert(texts.len());
        let file_texts = extract::extract_pages_text(path)?;
        rep.log(&format!(
            "Opened {} with {} pages",
            std::path::Path::new(path)
                .file_name()
                .map(|f| f.to_string_lossy().to_string())
                .unwrap_or_else(|| path.clone()),
            file_texts.len()
        ));
        for (pi, t) in file_texts.into_iter().enumerate() {
            source.push((fi, pi));
            texts.push(t);
        }
    }
    Ok(BatchInput {
        texts,
        source,
        boundaries,
    })
}

/// Tab 1: Shiprocket label processor.
pub fn process_shiprocket(
    rules: &RulesConfig,
    inputs: &[String],
    output: &str,
    is_4x4: bool,
    rep: &dyn Reporter,
) -> Result<ProcessStats, String> {
    rep.log("Starting PDF processing...");
    let batch = load_batch(inputs, rep)?;
    let texts = &batch.texts;
    let total_pages = texts.len();
    rep.log(&format!(
        "Processing {} file(s), {} pages total",
        inputs.len(),
        total_pages
    ));

    let mut marked_pages: Vec<(usize, String)> = Vec::new();
    let mut unmarked_pages: Vec<usize> = Vec::new();
    let mut total_counts = logic::ProductCounts::new();

    rep.log("Processing pages...");
    for (i, text) in texts.iter().enumerate() {
        if i % 25 == 0 || i == total_pages - 1 {
            rep.progress(i + 1, total_pages);
            rep.log(&format!("Processing page {}/{}", i + 1, total_pages));
        }
        let lines: Vec<&str> = text.lines().collect();
        let sku_labels = logic::extract_skus_from_page(rules, &lines);

        if sku_labels.is_empty() {
            unmarked_pages.push(i);
            continue;
        }

        let label_text = sku_labels
            .iter()
            .map(|(_, l)| l.as_str())
            .collect::<Vec<_>>()
            .join(" | ");
        marked_pages.push((i, label_text));

        logic::merge_counts(&mut total_counts, logic::count_products(rules, &sku_labels));
    }

    rep.log(&format!(
        "Found {} marked pages and {} unmarked pages",
        marked_pages.len(),
        unmarked_pages.len()
    ));
    for (product, buckets) in &total_counts {
        rep.log(&format!("{} counts: {:?}", product, buckets));
    }

    rep.log("Grouping and ordering pages...");
    let final_order = logic::group_pages(
        rules,
        &marked_pages,
        &unmarked_pages,
        &HashSet::new(),
        &batch.boundaries,
    );

    rep.log("Creating final PDF...");
    let sr = &rules.shiprocket;
    let stamp_color = parse_hex_color(&sr.stamp_color);
    let last = final_order.len().saturating_sub(1);
    let specs: Vec<PageSpec> = final_order
        .iter()
        .enumerate()
        .map(|(out_idx, (idx, label))| PageSpec {
            src_file: batch.source[*idx].0,
            src_index: batch.source[*idx].1,
            annotations: label
                .as_ref()
                .map(|l| {
                    vec![Annot::Text {
                        x: sr.stamp_x,
                        y: sr.stamp_y,
                        from_bottom: false,
                        text: l.replace('→', ">"),
                        font: Font::CourierBold,
                        size: sr.stamp_size,
                        color: stamp_color,
                    }]
                })
                .unwrap_or_default(),
            crop_bottom_pt: (is_4x4 && !(sr.crop_skip_last_page && out_idx == last))
                .then_some(sr.crop_mm * MM_TO_PT),
        })
        .collect();

    rep.log("Saving output file...");
    write::build_output(inputs, output, &specs)?;
    rep.log("PDF processing completed successfully!");

    Ok(ProcessStats {
        total_pages,
        marked: marked_pages.len(),
        unmarked: unmarked_pages.len(),
        counts: total_counts,
    })
}

fn compile_or_default(pattern: &str, default: &str) -> Regex {
    Regex::new(pattern).unwrap_or_else(|_| Regex::new(default).unwrap())
}

fn phone_annotations(
    mudoc: &MuDocument,
    page_text: &str,
    page_num: usize,
    pattern: &Regex,
    note: &str,
) -> Result<Vec<Annot>, String> {
    let mut annotations = Vec::new();
    for line in page_text.lines() {
        let line_str = line.trim();
        let line_upper = line_str.to_uppercase();
        if pattern.is_match(&line_upper) {
            let rects = extract::search_rects(mudoc, page_num as i32, line_str)?;
            for rect in rects {
                let (x0, y0, x1, y1) =
                    (rect.x0 as f64, rect.y0 as f64, rect.x1 as f64, rect.y1 as f64);
                annotations.push(Annot::Line {
                    x0,
                    y0: y1 + 1.0,
                    x1,
                    y1: y1 + 1.0,
                    width: 2.0,
                });
                annotations.push(Annot::Line {
                    x0,
                    y0: y0 - 1.0,
                    x1,
                    y1: y0 - 1.0,
                    width: 2.0,
                });
                annotations.push(Annot::Text {
                    x: x1 + 10.0,
                    y: y1 - 2.0,
                    from_bottom: false,
                    text: note.to_string(),
                    font: Font::HelveticaBold,
                    size: 12.0,
                    color: BLACK,
                });
            }
        }
    }
    Ok(annotations)
}

fn log_sorted_pages(
    rules: &RulesConfig,
    rep: &dyn Reporter,
    pages: &[(usize, Vec<logic::StProduct>)],
) {
    rep.log(&format!("\nSorted order for {} pages:", pages.len()));
    for (idx, (page_num, products)) in pages.iter().enumerate() {
        let details: Vec<String> = products
            .iter()
            .map(|p| format!("{} qty {}", logic::name_for_code(rules, p.0), p.1))
            .collect();
        rep.log(&format!(
            "  {}. Page {}: {}",
            idx + 1,
            page_num + 1,
            details.join(" | ")
        ));
    }
}

/// Tab 3: ST Courier labels — keeps only pages with recognized products,
/// sorted by product family/qty, with the Deliver-To phone highlighted.
pub fn process_st(
    rules: &RulesConfig,
    inputs: &[String],
    output: &str,
    rep: &dyn Reporter,
) -> Result<ProcessStats, String> {
    rep.log("Starting ST PDF processing...");
    let batch = load_batch(inputs, rep)?;
    let texts = &batch.texts;
    let total_pages = texts.len();
    rep.log(&format!(
        "Processing {} file(s), {} pages total",
        inputs.len(),
        total_pages
    ));

    let mut marked_pages: Vec<(usize, Vec<logic::StProduct>)> = Vec::new();

    rep.log("Processing pages...");
    for (i, text) in texts.iter().enumerate() {
        if i % 25 == 0 || i == total_pages - 1 {
            rep.progress(i + 1, total_pages);
            rep.log(&format!("Processing page {}/{}", i + 1, total_pages));
        }
        let products = logic::extract_st_products(rules, text);
        if !products.is_empty() {
            marked_pages.push((i, products));
        }
    }

    rep.log(&format!("Found {} pages with products", marked_pages.len()));
    rep.log("Sorting pages by product and quantity...");
    logic::sort_st_marked_pages(&mut marked_pages);
    log_sorted_pages(rules, rep, &marked_pages);

    rep.log("Creating new PDF with reordered pages...");
    let mudocs: Vec<MuDocument> = inputs
        .iter()
        .map(|p| MuDocument::open(p).map_err(|e| e.to_string()))
        .collect::<Result<_, _>>()?;
    let phone_re = compile_or_default(&rules.st.phone_pattern, r"^PH(?:ONE)?\s*:\s*\+?\d");

    let mut specs: Vec<PageSpec> = Vec::with_capacity(marked_pages.len());
    for (page_num, _) in &marked_pages {
        let (src_file, src_index) = batch.source[*page_num];
        specs.push(PageSpec {
            src_file,
            src_index,
            annotations: phone_annotations(
                &mudocs[src_file],
                &texts[*page_num],
                src_index,
                &phone_re,
                &rules.st.phone_note,
            )?,
            crop_bottom_pt: None,
        });
    }

    write::build_output(inputs, output, &specs)?;
    rep.log("PDF processing completed successfully!");

    Ok(ProcessStats {
        total_pages,
        marked: marked_pages.len(),
        unmarked: total_pages - marked_pages.len(),
        counts: logic::ProductCounts::new(),
    })
}

/// Tab 4: Delhivery Direct — extracts product lines by keyword rules,
/// sorts pages like the ST tab, stamps a family marker near the bottom
/// and highlights phone lines.
pub fn process_delhivery(
    rules: &RulesConfig,
    inputs: &[String],
    output: &str,
    rep: &dyn Reporter,
) -> Result<ProcessStats, String> {
    rep.log("Starting Delhivery Direct PDF processing...");
    let batch = load_batch(inputs, rep)?;
    let texts = &batch.texts;
    let total_pages = texts.len();
    rep.log(&format!(
        "Processing {} file(s), {} pages total",
        inputs.len(),
        total_pages
    ));

    let mut marked_pages: Vec<(usize, Vec<logic::StProduct>)> = Vec::new();

    rep.log("Processing pages...");
    for (i, text) in texts.iter().enumerate() {
        if i % 25 == 0 || i == total_pages - 1 {
            rep.progress(i + 1, total_pages);
            rep.log(&format!("Processing page {}/{}", i + 1, total_pages));
        }
        let products = logic::extract_delhivery_products(rules, text);
        if !products.is_empty() {
            marked_pages.push((i, products));
        }
    }

    rep.log(&format!(
        "Found {} pages with recognized products",
        marked_pages.len()
    ));
    rep.log("Sorting pages by product and quantity...");
    logic::sort_st_marked_pages(&mut marked_pages);
    log_sorted_pages(rules, rep, &marked_pages);

    rep.log("Creating new PDF with reordered pages...");
    let mudocs: Vec<MuDocument> = inputs
        .iter()
        .map(|p| MuDocument::open(p).map_err(|e| e.to_string()))
        .collect::<Result<_, _>>()?;
    let dd = &rules.delhivery;
    let stamp_color = parse_hex_color(&dd.stamp_color);
    let phone_re = compile_or_default(&dd.phone_pattern, r"^(PH|PHONE|MOBILE)\s*[:\-]?\s*\+?\d");

    let mut specs: Vec<PageSpec> = Vec::with_capacity(marked_pages.len());
    for (page_num, products) in &marked_pages {
        let (src_file, src_index) = batch.source[*page_num];
        let mut annotations = Vec::new();

        if !products.is_empty() {
            let label_parts: Vec<String> = products
                .iter()
                .map(|(code, qty, _)| {
                    logic::format_product_label(logic::stamp_label_for_code(rules, *code), *qty)
                })
                .collect();
            annotations.push(Annot::Text {
                x: dd.stamp_x,
                y: dd.stamp_from_bottom,
                from_bottom: true,
                text: label_parts.join(" | "),
                font: Font::CourierBold,
                size: dd.stamp_size,
                color: stamp_color,
            });
        }

        annotations.extend(phone_annotations(
            &mudocs[src_file],
            &texts[*page_num],
            src_index,
            &phone_re,
            &dd.phone_note,
        )?);

        specs.push(PageSpec {
            src_file,
            src_index,
            annotations,
            crop_bottom_pt: None,
        });
    }

    write::build_output(inputs, output, &specs)?;
    rep.log("PDF processing completed successfully!");

    Ok(ProcessStats {
        total_pages,
        marked: marked_pages.len(),
        unmarked: total_pages - marked_pages.len(),
        counts: logic::ProductCounts::new(),
    })
}
