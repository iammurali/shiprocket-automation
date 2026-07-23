//! Manual courier label PDF generation (port of generate_courier_labels).
//! Builds 4x6 (288x432) or 4x4 (288x288) label pages from scratch with lopdf.

use crate::config::{parse_hex_color, CourierRules};
use lopdf::{dictionary, Dictionary, Document, Object, Stream};
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct QueueOrder {
    pub order_id: String,
    pub phone: String,
    pub items: String,
    pub address: String,
}

// Helvetica-Bold AFM widths for ASCII 32..=126 (per 1000 units)
const HELV_BOLD_WIDTHS: [i32; 95] = [
    278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556,
    556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722,
    722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722,
    667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611,
    611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556,
    500, 389, 280, 389, 584,
];

fn text_width(text: &str, size: f64) -> f64 {
    let mut w = 0i64;
    for c in text.chars() {
        let cc = c as u32;
        let idx = if (32..=126).contains(&cc) {
            (cc - 32) as usize
        } else {
            0
        };
        w += HELV_BOLD_WIDTHS[idx] as i64;
    }
    w as f64 * size / 1000.0
}

fn escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '(' => out.push_str("\\("),
            ')' => out.push_str("\\)"),
            '\\' => out.push_str("\\\\"),
            c if (c as u32) < 256 => out.push(c),
            _ => out.push('?'),
        }
    }
    out
}

struct ContentBuilder {
    ops: String,
    page_h: f64,
}

impl ContentBuilder {
    fn new(page_h: f64) -> Self {
        Self {
            ops: String::new(),
            page_h,
        }
    }
    /// (x, y) = fitz coords, y measured from top; y is the text baseline
    fn text(&mut self, x: f64, y: f64, font: &str, size: f64, color: (f64, f64, f64), s: &str) {
        let py = self.page_h - y;
        self.ops.push_str(&format!(
            "q\nBT\n/{font} {size} Tf\n{} {} {} rg\n{x:.2} {py:.2} Td\n({}) Tj\nET\nQ\n",
            color.0,
            color.1,
            color.2,
            escape(s)
        ));
    }
    fn line(&mut self, x0: f64, y0: f64, x1: f64, y1: f64) {
        let a = self.page_h - y0;
        let b = self.page_h - y1;
        self.ops.push_str(&format!(
            "q\n1 w\n0 G\n{x0:.2} {a:.2} m\n{x1:.2} {b:.2} l\nS\nQ\n"
        ));
    }
    fn rect(&mut self, x0: f64, y0: f64, x1: f64, y1: f64) {
        // fitz rect -> pdf: lower-left at (x0, page_h - y1)
        let py = self.page_h - y1;
        let w = x1 - x0;
        let h = y1 - y0;
        self.ops.push_str(&format!(
            "q\n1 w\n0 G\n{x0:.2} {py:.2} {w:.2} {h:.2} re\nS\nQ\n"
        ));
    }
    /// place image; fitz rect (top-left coords)
    fn image(&mut self, name: &str, x0: f64, y0: f64, x1: f64, y1: f64) {
        let w = x1 - x0;
        let h = y1 - y0;
        let py = self.page_h - y1;
        self.ops.push_str(&format!(
            "q\n{w:.2} 0 0 {h:.2} {x0:.2} {py:.2} cm\n/{name} Do\nQ\n"
        ));
    }
}

pub struct Logo {
    pub rgb: Vec<u8>,
    pub width: u32,
    pub height: u32,
}

pub fn load_logo(path: &std::path::Path) -> Option<Logo> {
    let img = image::open(path).ok()?;
    let rgba = img.to_rgba8();
    let (w, h) = (rgba.width(), rgba.height());
    // composite alpha over white (labels have white background)
    let mut rgb = Vec::with_capacity((w * h * 3) as usize);
    for px in rgba.pixels() {
        let a = px[3] as u32;
        for i in 0..3 {
            let v = (px[i] as u32 * a + 255 * (255 - a)) / 255;
            rgb.push(v as u8);
        }
    }
    Some(Logo {
        rgb,
        width: w,
        height: h,
    })
}

pub fn generate_labels(
    rules: &CourierRules,
    orders: &[QueueOrder],
    is_4x4: bool,
    logo: Option<&Logo>,
    output_path: &std::path::Path,
) -> Result<(), String> {
    let title_color = parse_hex_color(&rules.title_color);
    let mut doc = Document::with_version("1.5");

    let helv = doc.add_object(dictionary! {
        "Type" => "Font", "Subtype" => "Type1",
        "BaseFont" => "Helvetica", "Encoding" => "WinAnsiEncoding",
    });
    let helv_bold = doc.add_object(dictionary! {
        "Type" => "Font", "Subtype" => "Type1",
        "BaseFont" => "Helvetica-Bold", "Encoding" => "WinAnsiEncoding",
    });

    let logo_xobj = logo.map(|l| {
        let stream = Stream::new(
            dictionary! {
                "Type" => "XObject",
                "Subtype" => "Image",
                "Width" => l.width as i64,
                "Height" => l.height as i64,
                "ColorSpace" => "DeviceRGB",
                "BitsPerComponent" => 8,
            },
            l.rgb.clone(),
        );
        doc.add_object(stream)
    });

    let mut font_dict = Dictionary::new();
    font_dict.set("F1", Object::Reference(helv));
    font_dict.set("F2", Object::Reference(helv_bold));
    let mut resources = dictionary! { "Font" => Object::Dictionary(font_dict) };
    if let Some(xid) = logo_xobj {
        let mut xdict = Dictionary::new();
        xdict.set("Im0", Object::Reference(xid));
        resources.set("XObject", Object::Dictionary(xdict));
    }
    let resources_id = doc.add_object(resources);

    let pages_root_id = doc.new_object_id();
    let mut kids: Vec<Object> = Vec::new();

    let page_height: f64 = if is_4x4 { 288.0 } else { 432.0 };

    for order in orders {
        let mut cb = ContentBuilder::new(page_height);

        // Border box
        cb.rect(10.0, 10.0, 278.0, page_height - 10.0);

        let mut y: f64;
        if let Some(l) = logo {
            let logo_h: f64 = if is_4x4 { 35.0 } else { 50.0 };
            // keep proportions inside rect (94, 10, 194, 10+logo_h), centered
            let scale = (100.0 / l.width as f64).min(logo_h / l.height as f64);
            let w = l.width as f64 * scale;
            let h = l.height as f64 * scale;
            let x0 = 94.0 + (100.0 - w) / 2.0;
            let top = 10.0 + (logo_h - h) / 2.0;
            cb.image("Im0", x0, top, x0 + w, top + h);

            y = if is_4x4 {
                10.0 + logo_h + 2.0
            } else {
                10.0 + logo_h + 5.0
            };

            let text_h: f64 = if is_4x4 { 25.0 } else { 30.0 };
            let text_size: f64 = if is_4x4 { 14.0 } else { 18.0 };
            // centered title (textbox align=center equivalent)
            let title = rules.brand_name.as_str();
            let tw = text_width(title, text_size);
            let tx = (288.0 - tw) / 2.0;
            cb.text(tx, y + text_size, "F2", text_size, title_color, title);
            y += text_h - 5.0;
        } else {
            y = 30.0;
            cb.text(
                20.0,
                y,
                "F1",
                14.0,
                (0.0, 0.0, 0.0),
                &rules.brand_name.to_uppercase(),
            );
            y += 25.0;
        }

        // Divider
        cb.line(10.0, y, 278.0, y);
        y += if is_4x4 { 10.0 } else { 20.0 };

        // Order details
        cb.text(
            20.0,
            y,
            "F1",
            10.0,
            (0.0, 0.0, 0.0),
            &format!("Order ID: {}", order.order_id),
        );
        y += if is_4x4 { 12.0 } else { 15.0 };

        if !order.items.is_empty() {
            let item_font_size = if is_4x4 { 8.0 } else { 10.0 };
            cb.text(
                20.0,
                y,
                "F1",
                item_font_size,
                (0.0, 0.0, 0.0),
                &format!("Items: {}", order.items),
            );
            y += if is_4x4 { 15.0 } else { 20.0 };
        }

        cb.line(10.0, y, 278.0, y);
        y += if is_4x4 { 10.0 } else { 20.0 };

        // To address
        cb.text(20.0, y, "F2", 11.0, (0.0, 0.0, 0.0), "To:");
        y += if is_4x4 { 12.0 } else { 15.0 };

        for line in order.address.split('\n') {
            cb.text(25.0, y, "F1", 10.0, (0.0, 0.0, 0.0), line);
            y += if is_4x4 { 10.0 } else { 12.0 };
        }

        let phone_val = order.phone.trim();
        if !phone_val.is_empty() && !phone_val.to_lowercase().contains("xxxx") {
            y += 5.0;
            cb.text(
                25.0,
                y,
                "F2",
                10.0,
                (0.0, 0.0, 0.0),
                &format!("Ph: {}", phone_val),
            );
        }

        // From address block
        let final_from = if is_4x4 {
            rules.from_address_4x4.as_str()
        } else {
            rules.from_address.as_str()
        };
        let from_area_height: f64 = if is_4x4 { 55.0 } else { 70.0 };
        let from_y_start: f64 = if is_4x4 {
            page_height - from_area_height
        } else {
            y.max(250.0)
        };

        cb.line(10.0, from_y_start, 278.0, from_y_start);

        let mut from_text_y = from_y_start + if is_4x4 { 10.0 } else { 15.0 };
        let from_font_size = if is_4x4 { 8.0 } else { 9.0 };
        for line in final_from.split('\n') {
            cb.text(20.0, from_text_y, "F1", from_font_size, (0.0, 0.0, 0.0), line);
            from_text_y += if is_4x4 { 10.0 } else { 12.0 };
        }

        let content_id = doc.add_object(Stream::new(dictionary! {}, cb.ops.into_bytes()));
        let page_id = doc.add_object(dictionary! {
            "Type" => "Page",
            "Parent" => Object::Reference(pages_root_id),
            "MediaBox" => Object::Array(vec![0.into(), 0.into(), 288.into(), Object::Real(page_height as f32)]),
            "Resources" => Object::Reference(resources_id),
            "Contents" => Object::Reference(content_id),
        });
        kids.push(Object::Reference(page_id));
    }

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

    doc.compress();
    doc.save(output_path)
        .map_err(|e| format!("Failed to save labels PDF: {e}"))?;
    Ok(())
}
