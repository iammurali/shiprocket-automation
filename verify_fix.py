import fitz
import os

def create_dummy_logo():
    # Create a simple red square image as dummy logo
    import zlib
    
    # Minimal 1x1 PNG pixel
    # Not using PIL to avoid dependency issues if not installed, though likely is.
    # Actually, let's just use a simple colored rectangle in PyMuPDF if file missing, 
    # but the code expects a file stream.
    # Let's try to create a real small PNG file.
    if not os.path.exists("Logo.png"):
        print("Creating dummy Logo.png...")
        # 1x1 white pixel
        with open("Logo.png", "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0bIDAT\x08\xd7c\xf8\x0f\x04\x00\x09\xfb\x03\xfd\xe3\x55\xf2\x9c\x00\x00\x00\x00IEND\xaeB`\x82')

def generate_label(output_filename="test_label.pdf"):
    create_dummy_logo()
    
    try:
        with open("Logo.png", "rb") as f:
            logo_data = f.read()
    except:
        logo_data = None
        
    doc = fitz.open()
    page = doc.new_page(width=288, height=432)
    
    # Draw Box
    rect = fitz.Rect(10, 10, 278, 422)
    page.draw_rect(rect)
    
    y = 15
    if logo_data:
        # Centered Logo with aspect ratio fix
        logo_rect = fitz.Rect(94, 10, 194, 60)
        # FIX 1: keep_proportion=True
        page.insert_image(logo_rect, stream=logo_data, keep_proportion=True)
        
        y = 80 
        
        # Centered Bold Text
        # FIX 2: Increased height from 20 to 40
        text_rect = fitz.Rect(0, y, 288, y + 40)
        page.insert_textbox(text_rect, "Tulir Naturals", 
                          fontname="hebo", fontsize=20,
                          color=(0.1, 0.35, 0.1),
                          align=1) 
        y += 30 
    
    doc.save(output_filename)
    print(f"Generated {output_filename}")
    return output_filename

def verify_pdf(filename):
    doc = fitz.open(filename)
    page = doc[0]
    text = page.get_text()
    print("Extracted Text:")
    print(text)
    
    if "Tulir Naturals" in text:
        print("\nSUCCESS: 'Tulir Naturals' text found in PDF!")
    else:
        print("\nFAILURE: 'Tulir Naturals' text NOT found.")

if __name__ == "__main__":
    pdf_file = generate_label()
    verify_pdf(pdf_file)
