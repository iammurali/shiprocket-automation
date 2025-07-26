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

# Lists to store page numbers and their labels (not page objects)
marked_pages: List[Tuple[int, str]] = []
unmarked_pages: List[int] = []

for i, page in enumerate(doc):
    text = page.get_text()
    print(f"Processing page {i + 1}")  # Debug: print the current page number
    
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
        # Store the page number and its label
        marked_pages.append((i, label_text))
    else:
        unmarked_pages.append(i)

# Create a new PDF with reordered pages
new_doc = fitz.open()

# Batch copy unmarked pages (more efficient)
if unmarked_pages:
    # Group consecutive pages for batch copying
    page_ranges = []
    start = unmarked_pages[0]
    end = start
    
    for page_num in unmarked_pages[1:]:
        if page_num == end + 1:
            end = page_num
        else:
            page_ranges.append((start, end))
            start = end = page_num
    page_ranges.append((start, end))
    
    # Copy pages in batches
    for start, end in page_ranges:
        new_doc.insert_pdf(doc, from_page=start, to_page=end)

# Add marked pages at the end with their labels
for page_num, label_text in marked_pages:
    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
    # Add label to the newly inserted page
    insert_point = fitz.Point(5, 250)
    new_doc[-1].insert_text(insert_point, label_text, 
                           fontname="Courier-Bold", fontsize=12, color=(1, 0, 0))

# Save with minimal optimization for speed
new_doc.save(output_pdf,
             deflate=False,    # Disable compression for speed
             garbage=1,        # Minimal garbage collection
             clean=True       # cleaning but slow
)

print(f"Modified PDF saved as {output_pdf} with marked pages moved to the end.")

# Close both documents
doc.close()
new_doc.close()