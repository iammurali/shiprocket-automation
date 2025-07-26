import fitz  # PyMuPDF
import re
from typing import List, Tuple

# SKU to product name mapping
sku_map = {
    "TN0001": "OIL",
    "TN0002": "Potli",
    "TN003": "Rollon"
}

# Open the original PDF
input_pdf = "input.pdf"
output_pdf = "output_modified.pdf"
doc = fitz.open(input_pdf)

# Lists to store pages and their labels
marked_pages: List[Tuple[fitz.Page, str]] = []
unmarked_pages: List[fitz.Page] = []

for i, page in enumerate(doc):
    text = page.get_text()
    print(f"Processing page {i + 1}")  # Debug: print the current page number
    print(text)  # Debug: print the text content of the page

    # Find all SKUs and their quantities
    lines = text.splitlines()
    sku_labels = []
    for idx, line in enumerate(lines):
        sku_match = re.search(r'SKU:\s*(\w+)', line)
        if sku_match:
            sku = sku_match.group(1)
            qty = 1
            # Try to get the next line for quantity
            if idx + 1 < len(lines):
                next_line = lines[idx + 1]
                qty_match = re.search(r'(\d+)', next_line)
                if qty_match:
                    qty = int(qty_match.group(1))
            # Add label if qty > 1 OR if SKU is not TN0001
            if qty > 1 or sku != "TN0001":
                product_name = sku_map.get(sku, "Unknown Product")
                # Only show quantity if it's greater than 1
                label_text = f"→ {product_name}x{qty}" if qty > 1 else f"→ {product_name}"
                sku_labels.append(label_text)

    if sku_labels:
        # Concatenate all labels
        label_text = " | ".join(sku_labels)
        # Store the page and its label for later
        marked_pages.append((page, label_text))
    else:
        unmarked_pages.append(page)

# Create a new PDF with reordered pages
new_doc = fitz.open()

# Enable compression
new_doc._compress = True

# Add all unmarked pages first
for page in unmarked_pages:
    new_doc.insert_pdf(doc, from_page=page.number, to_page=page.number)

# Add marked pages at the end with their labels
for page, label_text in marked_pages:
    new_doc.insert_pdf(doc, from_page=page.number, to_page=page.number)
    insert_point = fitz.Point(5, 250)
    new_doc[-1].insert_text(insert_point, label_text, fontname="Courier-Bold", fontsize=12, color=(1, 0, 0))

# Save with optimization
new_doc.save(output_pdf, 
    deflate=True,    # Use compression
    garbage=3,       # Remove all unused objects
    clean=True       # Clean redundant elements
)
print(f"Modified PDF saved as {output_pdf} with marked pages moved to the end.")

# Close both documents
doc.close()
new_doc.close()
