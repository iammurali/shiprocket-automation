# Shiprocket Label Processor — Tauri App

Native desktop port of `pdf_gui.py` (tkinter) built with **Tauri v2**. All PDF
processing runs in **Rust**; the UI is a lightweight Vite + TypeScript frontend.

## Features (parity with the Python app)

| Tab | What it does |
|-----|--------------|
| **Label Processor** | Shiprocket label PDFs: extracts SKUs per page, counts Oil/Potli packs, groups & reorders pages, stamps red product markers, optional 4×4 crop (bottom 50 mm removed on all but the last page) |
| **Courier PDF Generator** | Order queue with Shiprocket order lookup, manual 4×6 / 4×4 label generation with the Tulir Naturals logo (saved to `~/Downloads`), Shopify order-note updates |
| **ST Courier Labels** | Keeps only pages with recognized ST products, sorts by product family + qty, highlights "PH:" phone lines with over/underline + "CALL THIS NUMBER" |
| **Delhivery Direct** | Extracts "Tulir Naturals …" product lines (SKU fallback), ST-style sorting, red family marker near the page bottom, phone highlighting |

All three processor tabs accept **multiple input PDFs at once** (multi-select in
the file picker): pages from every file are pooled and sorted/grouped as one
batch into a single output PDF. The unmarked+marked page pairing in tab 1 never
spans two source files. The courier order queue supports checkbox multi-select
with select-all and "Remove Selected".

Per-tab default output folders live under `~/Documents/Shiprocket Label Processor/`
(persisted across sessions). Shiprocket/Shopify credentials are stored in the OS
config dir (`~/Library/Application Support/shiprocket-label-processor/config.json` on macOS).

## Configuration panel (no-code rules)

The **⚙ Configuration** tab makes the label logic data-driven — when a label
format changes or a new product launches, edit settings instead of code:

- **Products**: name, stamp label, canonical name, match keywords, SKUs,
  stats tracking; add/remove/reorder (order = sort & grouping priority; more
  specific keyword sets are matched before broader ones automatically).
- **Label Processor**: stamp position/size/color, 4×4 crop mm, grouping depth.
- **ST Courier / Delhivery**: line filters, skip rules, qty regex patterns,
  phone-highlight pattern and note text, stamp placement.
- **Courier Label**: brand name, title color, both from-addresses.

Everything is stored in the same `config.json` (`rules` key) with
"Reset rules to defaults" restoring the built-in behavior. The `extract-test`
harness honors a `RULES_JSON=<path>` env var pointing at a rules JSON for
headless testing of custom configurations.

## Implementation notes

- **Text extraction** uses the `mupdf` crate — the same engine PyMuPDF wraps.
  Extraction was validated **byte-identical** to PyMuPDF across all sample PDFs
  (503 pages), so page parsing/ordering matches the Python app exactly.
- **Document surgery** (page reordering, crop boxes, stamps, label generation)
  uses `lopdf`.
- Output PDFs were verified page-by-page against the Python implementation on
  `input.pdf`, `input2.pdf`, `input3.pdf` for the Shiprocket and Delhivery
  pipelines (identical page order, stamps, and highlights).
- Two deliberate fixes over the current Python code:
  - Stamps use `>` instead of `→` (base-14 fonts can't encode `→`; Python
    renders it as a garbled `·`).
  - The Python 4×4 crop references `fitz.mupdf.PIXELSPERMILLIMETER`, which
    doesn't exist (the feature crashes); the Rust port applies the intended
    50 mm crop.

## Development

```sh
npm install
npm run tauri dev      # run with hot reload
npm run tauri build    # produce .app / .dmg (bundle in src-tauri/target/release/bundle)
```

`src-tauri/target/debug/extract-test` is a headless CLI harness used to verify
the pipelines against the Python implementation:

```sh
extract-test dump <pdf>                   # per-page text as JSON
extract-test shiprocket <in> <out> [4x4]  # tab-1 pipeline
extract-test delhivery <in> <out>         # tab-4 pipeline
extract-test st <in> <out>                # tab-3 pipeline
extract-test labels <orders.json> <out> [4x4] [logo.png]
```
