import fitz  # PyMuPDF
import re

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

for i, page in enumerate(doc):
    text = page.get_text()
    print(f"Processing page {i + 1}")  # Debug: print the current page number
    print(text)  # Debug: print the text content of the page
    # if i + 1 == 170:
    #     break  # Stop processing after page 170 for debugging

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
        insert_point = fitz.Point(5, 250)  # Tune this based on actual PDF layout
        page.insert_text(insert_point, label_text, fontname="hebo", fontsize=12, color=(0, 0, 0))  # Red text

doc.save(output_pdf)
print(f"Modified PDF saved as {output_pdf}")
