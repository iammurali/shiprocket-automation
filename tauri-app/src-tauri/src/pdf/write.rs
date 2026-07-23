//! Document surgery with lopdf: reorder pages, crop, stamp annotations.
//! Annotation coordinates are in fitz space (top-left origin, relative to the
//! page's final cropbox) so pipelines can share PyMuPDF-style coordinates.

use lopdf::{dictionary, Dictionary, Document, Object, ObjectId, Stream};

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum Font {
    CourierBold,
    HelveticaBold,
}

impl Font {
    fn base_font(&self) -> &'static str {
        match self {
            Font::CourierBold => "Courier-Bold",
            Font::HelveticaBold => "Helvetica-Bold",
        }
    }
    fn res_name(&self) -> &'static str {
        match self {
            Font::CourierBold => "FCB0",
            Font::HelveticaBold => "FHB0",
        }
    }
}

#[derive(Debug, Clone)]
pub enum Annot {
    Text {
        x: f64,
        /// distance from the top of the cropbox (fitz-style), or from the
        /// bottom when `from_bottom` is set
        y: f64,
        from_bottom: bool,
        text: String,
        font: Font,
        size: f64,
        color: (f64, f64, f64),
    },
    Line {
        x0: f64,
        y0: f64,
        x1: f64,
        y1: f64,
        width: f64,
    },
}

#[derive(Debug, Clone)]
pub struct PageSpec {
    /// index into the list of input files passed to build_output
    pub src_file: usize,
    /// 0-based page index within that source document
    pub src_index: usize,
    pub annotations: Vec<Annot>,
    /// remove this many points from the visual bottom of the page
    pub crop_bottom_pt: Option<f64>,
}

fn inherited(doc: &Document, page_id: ObjectId, key: &[u8]) -> Option<Object> {
    let mut cur = page_id;
    for _ in 0..64 {
        let dict = doc.get_object(cur).ok()?.as_dict().ok()?;
        if let Ok(v) = dict.get(key) {
            return Some(v.clone());
        }
        match dict.get(b"Parent") {
            Ok(Object::Reference(p)) => cur = *p,
            _ => return None,
        }
    }
    None
}

fn rect_from_obj(doc: &Document, obj: &Object) -> Option<[f64; 4]> {
    let arr = match obj {
        Object::Reference(id) => doc.get_object(*id).ok()?.as_array().ok()?.clone(),
        Object::Array(a) => a.clone(),
        _ => return None,
    };
    if arr.len() != 4 {
        return None;
    }
    let mut out = [0f64; 4];
    for (i, v) in arr.iter().enumerate() {
        out[i] = match v {
            Object::Integer(n) => *n as f64,
            Object::Real(r) => *r as f64,
            _ => return None,
        };
    }
    // normalize so ll <= ur
    let (x0, x1) = (out[0].min(out[2]), out[0].max(out[2]));
    let (y0, y1) = (out[1].min(out[3]), out[1].max(out[3]));
    Some([x0, y0, x1, y1])
}

fn escape_pdf_string(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '(' => out.push_str("\\("),
            ')' => out.push_str("\\)"),
            '\\' => out.push_str("\\\\"),
            c if (c as u32) < 256 => out.push(c),
            // non-latin1 chars can't be shown in base14 WinAnsi; replace
            _ => out.push('?'),
        }
    }
    out
}

fn fmt(v: f64) -> String {
    if (v - v.round()).abs() < 1e-6 {
        format!("{}", v.round() as i64)
    } else {
        format!("{:.3}", v)
    }
}

/// Build the annotation content stream. cb = final cropbox [x0,y0,x1,y1].
fn annots_to_ops(annots: &[Annot], cb: [f64; 4]) -> String {
    let mut ops = String::new();
    for a in annots {
        match a {
            Annot::Text {
                x,
                y,
                from_bottom,
                text,
                font,
                size,
                color,
            } => {
                let px = cb[0] + x;
                let py = if *from_bottom { cb[1] + y } else { cb[3] - y };
                ops.push_str(&format!(
                    "q\nBT\n/{} {} Tf\n{} {} {} rg\n{} {} Td\n({}) Tj\nET\nQ\n",
                    font.res_name(),
                    fmt(*size),
                    fmt(color.0),
                    fmt(color.1),
                    fmt(color.2),
                    fmt(px),
                    fmt(py),
                    escape_pdf_string(text)
                ));
            }
            Annot::Line {
                x0,
                y0,
                x1,
                y1,
                width,
            } => {
                let ax = cb[0] + x0;
                let ay = cb[3] - y0;
                let bx = cb[0] + x1;
                let by = cb[3] - y1;
                ops.push_str(&format!(
                    "q\n{} w\n0 G\n{} {} m\n{} {} l\nS\nQ\n",
                    fmt(*width),
                    fmt(ax),
                    fmt(ay),
                    fmt(bx),
                    fmt(by)
                ));
            }
        }
    }
    ops
}

fn annot_fonts(annots: &[Annot]) -> Vec<Font> {
    let mut fonts = Vec::new();
    for a in annots {
        if let Annot::Text { font, .. } = a {
            if !fonts.contains(font) {
                fonts.push(*font);
            }
        }
    }
    fonts
}

/// Rebuild pages from one or more `input_paths` in `specs` order (dropping
/// others), applying crops and annotations, and save to `output_path`.
/// Multiple sources are merged by renumbering each document's objects into a
/// disjoint id range and rebuilding a fresh page tree.
pub fn build_output(
    input_paths: &[String],
    output_path: &str,
    specs: &[PageSpec],
) -> Result<(), String> {
    if specs.is_empty() {
        return Err("cannot save with zero pages — no matching pages found".into());
    }
    if input_paths.is_empty() {
        return Err("no input files given".into());
    }

    // Load every source, renumber into disjoint object-id ranges and pool
    // all objects into one document.
    let mut doc = Document::with_version("1.5");
    let mut page_maps: Vec<std::collections::BTreeMap<u32, ObjectId>> = Vec::new();
    let mut max_id: u32 = 0;
    for path in input_paths {
        let mut src = Document::load(path)
            .map_err(|e| format!("Failed to load PDF {}: {e}", path))?;
        src.renumber_objects_with(max_id + 1);
        max_id = src.max_id;
        page_maps.push(src.get_pages()); // 1-based page number -> ObjectId
        doc.objects.extend(std::mem::take(&mut src.objects));
    }
    doc.max_id = max_id;

    // Fresh page tree + catalog (source catalogs get pruned as unreferenced)
    let pages_root_id = doc.new_object_id();

    // Font objects created lazily, shared across pages
    let mut font_ids: std::collections::HashMap<&'static str, ObjectId> =
        std::collections::HashMap::new();

    let mut kids: Vec<Object> = Vec::with_capacity(specs.len());

    for spec in specs {
        let page_no = (spec.src_index + 1) as u32;
        let &page_id = page_maps
            .get(spec.src_file)
            .ok_or_else(|| format!("Input file {} not found", spec.src_file))?
            .get(&page_no)
            .ok_or_else(|| format!("Page {} not found in input {}", page_no, spec.src_file + 1))?;

        // 1. Push down inheritable attributes so reparenting is safe
        for key in [b"Resources".as_slice(), b"MediaBox", b"CropBox", b"Rotate"] {
            let has = doc
                .get_object(page_id)
                .ok()
                .and_then(|o| o.as_dict().ok())
                .map(|d| d.has(key))
                .unwrap_or(false);
            if !has {
                if let Some(v) = inherited(&doc, page_id, key) {
                    if let Ok(Object::Dictionary(ref mut d)) = doc.get_object_mut(page_id) {
                        d.set(key.to_vec(), v);
                    }
                }
            }
        }

        // 2. Effective boxes
        let media = doc
            .get_object(page_id)
            .ok()
            .and_then(|o| o.as_dict().ok())
            .and_then(|d| d.get(b"MediaBox").ok().cloned())
            .and_then(|o| rect_from_obj(&doc, &o))
            .unwrap_or([0.0, 0.0, 612.0, 792.0]);
        let mut crop = doc
            .get_object(page_id)
            .ok()
            .and_then(|o| o.as_dict().ok())
            .and_then(|d| d.get(b"CropBox").ok().cloned())
            .and_then(|o| rect_from_obj(&doc, &o))
            .unwrap_or(media);

        // 3. Crop bottom (like PyMuPDF set_cropbox keeping the top part)
        if let Some(remove_pt) = spec.crop_bottom_pt {
            let height = crop[3] - crop[1];
            if height > remove_pt + 0.1 {
                crop = [crop[0], crop[1] + remove_pt, crop[2], crop[3]];
                if let Ok(Object::Dictionary(ref mut d)) = doc.get_object_mut(page_id) {
                    d.set(
                        b"CropBox".to_vec(),
                        Object::Array(vec![
                            Object::Real(crop[0] as f32),
                            Object::Real(crop[1] as f32),
                            Object::Real(crop[2] as f32),
                            Object::Real(crop[3] as f32),
                        ]),
                    );
                }
            }
        }

        // 4. Annotations -> appended content stream
        if !spec.annotations.is_empty() {
            // ensure fonts exist in doc + page resources
            let fonts = annot_fonts(&spec.annotations);
            for f in &fonts {
                if !font_ids.contains_key(f.res_name()) {
                    let fid = doc.add_object(dictionary! {
                        "Type" => "Font",
                        "Subtype" => "Type1",
                        "BaseFont" => f.base_font(),
                        "Encoding" => "WinAnsiEncoding",
                    });
                    font_ids.insert(f.res_name(), fid);
                }
            }

            // resolve Resources (dict inline or via reference)
            let res_obj = doc
                .get_object(page_id)
                .ok()
                .and_then(|o| o.as_dict().ok())
                .and_then(|d| d.get(b"Resources").ok().cloned());

            let ensure_fonts = |res: &mut Dictionary,
                                font_ids: &std::collections::HashMap<&'static str, ObjectId>|
             -> Result<(), String> {
                let mut font_dict = match res.get(b"Font") {
                    Ok(Object::Dictionary(d)) => d.clone(),
                    Ok(Object::Reference(_)) => {
                        // handled by caller resolving; simple case: replace with clone
                        Dictionary::new()
                    }
                    _ => Dictionary::new(),
                };
                for f in &fonts {
                    if !font_dict.has(f.res_name().as_bytes()) {
                        font_dict.set(
                            f.res_name().as_bytes().to_vec(),
                            Object::Reference(font_ids[f.res_name()]),
                        );
                    }
                }
                res.set(b"Font".to_vec(), Object::Dictionary(font_dict));
                Ok(())
            };

            match res_obj {
                Some(Object::Reference(rid)) => {
                    // deal with Font-as-reference inside referenced Resources
                    let font_ref = {
                        let rd = doc
                            .get_object(rid)
                            .and_then(|o| o.as_dict())
                            .map_err(|e| e.to_string())?;
                        match rd.get(b"Font") {
                            Ok(Object::Reference(fid)) => Some(*fid),
                            _ => None,
                        }
                    };
                    if let Some(fid) = font_ref {
                        if let Ok(Object::Dictionary(ref mut fd)) = doc.get_object_mut(fid) {
                            for f in &fonts {
                                if !fd.has(f.res_name().as_bytes()) {
                                    fd.set(
                                        f.res_name().as_bytes().to_vec(),
                                        Object::Reference(font_ids[f.res_name()]),
                                    );
                                }
                            }
                        }
                    } else if let Ok(Object::Dictionary(ref mut rd)) = doc.get_object_mut(rid) {
                        ensure_fonts(rd, &font_ids)?;
                    }
                }
                Some(Object::Dictionary(mut rd)) => {
                    let font_ref = match rd.get(b"Font") {
                        Ok(Object::Reference(fid)) => Some(*fid),
                        _ => None,
                    };
                    if let Some(fid) = font_ref {
                        if let Ok(Object::Dictionary(ref mut fd)) = doc.get_object_mut(fid) {
                            for f in &fonts {
                                if !fd.has(f.res_name().as_bytes()) {
                                    fd.set(
                                        f.res_name().as_bytes().to_vec(),
                                        Object::Reference(font_ids[f.res_name()]),
                                    );
                                }
                            }
                        }
                    } else {
                        ensure_fonts(&mut rd, &font_ids)?;
                    }
                    if let Ok(Object::Dictionary(ref mut d)) = doc.get_object_mut(page_id) {
                        d.set(b"Resources".to_vec(), Object::Dictionary(rd));
                    }
                }
                _ => {
                    let mut rd = Dictionary::new();
                    ensure_fonts(&mut rd, &font_ids)?;
                    if let Ok(Object::Dictionary(ref mut d)) = doc.get_object_mut(page_id) {
                        d.set(b"Resources".to_vec(), Object::Dictionary(rd));
                    }
                }
            }

            let ops = annots_to_ops(&spec.annotations, crop);
            let stream_id =
                doc.add_object(Stream::new(dictionary! {}, ops.into_bytes()));

            // append to Contents
            let contents = doc
                .get_object(page_id)
                .ok()
                .and_then(|o| o.as_dict().ok())
                .and_then(|d| d.get(b"Contents").ok().cloned());
            let new_contents = match contents {
                Some(Object::Array(mut arr)) => {
                    arr.push(Object::Reference(stream_id));
                    Object::Array(arr)
                }
                Some(Object::Reference(orig)) => Object::Array(vec![
                    Object::Reference(orig),
                    Object::Reference(stream_id),
                ]),
                _ => Object::Reference(stream_id),
            };
            if let Ok(Object::Dictionary(ref mut d)) = doc.get_object_mut(page_id) {
                d.set(b"Contents".to_vec(), new_contents);
            }
        }

        // 5. Reparent to root
        if let Ok(Object::Dictionary(ref mut d)) = doc.get_object_mut(page_id) {
            d.set(b"Parent".to_vec(), Object::Reference(pages_root_id));
        }
        kids.push(Object::Reference(page_id));
    }

    // Install the new pages root + catalog and point the trailer at them
    let count = kids.len() as i64;
    doc.objects.insert(
        pages_root_id,
        Object::Dictionary(dictionary! {
            "Type" => "Pages",
            "Kids" => Object::Array(kids),
            "Count" => Object::Integer(count),
        }),
    );
    let catalog_id = doc.add_object(dictionary! {
        "Type" => "Catalog",
        "Pages" => Object::Reference(pages_root_id),
    });
    doc.trailer.set("Root", Object::Reference(catalog_id));

    doc.prune_objects();
    doc.renumber_objects();
    doc.save(output_path)
        .map_err(|e| format!("Failed to save PDF: {e}"))?;
    Ok(())
}
