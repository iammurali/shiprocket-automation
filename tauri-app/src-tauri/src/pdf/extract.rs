//! Text extraction via MuPDF — reconstructs page text exactly like
//! PyMuPDF's get_text() (validated byte-identical on sample label PDFs).

use mupdf::{Document, Page, TextPageOptions};

pub fn page_text(page: &Page) -> Result<String, String> {
    let tp = page
        .to_text_page(TextPageOptions::empty())
        .map_err(|e| e.to_string())?;
    let mut out = String::new();
    for block in tp.blocks() {
        for line in block.lines() {
            for ch in line.chars() {
                if let Some(c) = ch.char() {
                    out.push(c);
                }
            }
            out.push('\n');
        }
    }
    Ok(out)
}

pub fn extract_pages_text(path: &str) -> Result<Vec<String>, String> {
    let doc = Document::open(path).map_err(|e| format!("Failed to open PDF: {e}"))?;
    let n = doc.page_count().map_err(|e| e.to_string())?;
    let mut pages = Vec::with_capacity(n as usize);
    for i in 0..n {
        let page = doc.load_page(i).map_err(|e| e.to_string())?;
        pages.push(page_text(&page)?);
    }
    Ok(pages)
}

#[derive(Debug, Clone, Copy)]
pub struct FitzRect {
    pub x0: f32,
    pub y0: f32,
    pub x1: f32,
    pub y1: f32,
}

/// Search for `needle` on a page; returns rects in fitz (top-left origin) coords,
/// equivalent to PyMuPDF's page.search_for().
pub fn search_rects(doc: &Document, page_index: i32, needle: &str) -> Result<Vec<FitzRect>, String> {
    let page = doc.load_page(page_index).map_err(|e| e.to_string())?;
    let quads = page.search(needle, 64).map_err(|e| e.to_string())?;
    Ok(quads
        .into_iter()
        .map(|q| FitzRect {
            x0: q.ul.x.min(q.ll.x),
            y0: q.ul.y.min(q.ur.y),
            x1: q.ur.x.max(q.lr.x),
            y1: q.ll.y.max(q.lr.y),
        })
        .collect())
}
