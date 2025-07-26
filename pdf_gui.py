import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz  # PyMuPDF
import re
import os
from typing import List, Tuple
import threading

class PDFProcessorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF Label Processor")
        self.root.geometry("600x400")
        self.root.resizable(True, True)
        
        # Variables
        self.input_file_path = tk.StringVar()
        self.output_file_path = tk.StringVar()
        self.processing = False
        
        # SKU to product name mapping
        self.sku_map = {
            "TN0001": "OIL",
            "TN0002": "Potli", 
            "TN003": "Rollon"
        }
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="PDF Label Processor", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Input file selection
        ttk.Label(main_frame, text="Input PDF File:").grid(row=1, column=0, sticky=tk.W, pady=5)
        
        input_frame = ttk.Frame(main_frame)
        input_frame.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        input_frame.columnconfigure(0, weight=1)
        
        self.input_entry = ttk.Entry(input_frame, textvariable=self.input_file_path, state="readonly")
        self.input_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(input_frame, text="Browse", command=self.browse_input_file).grid(row=0, column=1)
        
        # Output file selection
        ttk.Label(main_frame, text="Output PDF File:").grid(row=2, column=0, sticky=tk.W, pady=5)
        
        output_frame = ttk.Frame(main_frame)
        output_frame.grid(row=2, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        output_frame.columnconfigure(0, weight=1)
        
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output_file_path, state="readonly")
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 10))
        
        ttk.Button(output_frame, text="Browse", command=self.browse_output_file).grid(row=0, column=1)
        
        # Process button
        self.process_button = ttk.Button(main_frame, text="Process PDF", 
                                        command=self.process_pdf, style="Accent.TButton")
        self.process_button.grid(row=3, column=0, columnspan=3, pady=20)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready to process", 
                                     font=("Arial", 10))
        self.status_label.grid(row=5, column=0, columnspan=3, pady=10)
        
        # Log text area
        log_frame = ttk.LabelFrame(main_frame, text="Processing Log", padding="10")
        log_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(log_frame)
        text_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        self.log_text = tk.Text(text_frame, height=8, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Clear log button
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log).grid(row=1, column=0, pady=(10, 0))
        
    def browse_input_file(self):
        filename = filedialog.askopenfilename(
            title="Select Input PDF",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.input_file_path.set(filename)
            # Auto-generate output filename
            base_name = os.path.splitext(filename)[0]
            self.output_file_path.set(f"{base_name}_processed.pdf")
            
    def browse_output_file(self):
        filename = filedialog.asksaveasfilename(
            title="Save Output PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.output_file_path.set(filename)
            
    def log_message(self, message):
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
        
    def update_status(self, message):
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def process_pdf(self):
        if self.processing:
            return
            
        input_path = self.input_file_path.get()
        output_path = self.output_file_path.get()
        
        if not input_path:
            messagebox.showerror("Error", "Please select an input PDF file.")
            return
            
        if not output_path:
            messagebox.showerror("Error", "Please select an output PDF file.")
            return
            
        if not os.path.exists(input_path):
            messagebox.showerror("Error", "Input file does not exist.")
            return
            
        # Start processing in a separate thread
        self.processing = True
        self.process_button.config(state="disabled")
        self.progress.start()
        self.update_status("Processing...")
        self.clear_log()
        
        thread = threading.Thread(target=self._process_pdf_thread, 
                                args=(input_path, output_path))
        thread.daemon = True
        thread.start()
        
    def _process_pdf_thread(self, input_path, output_path):
        try:
            self.log_message("Starting PDF processing...")
            
            # Open the original PDF
            doc = fitz.open(input_path)
            self.log_message(f"Opened PDF with {len(doc)} pages")
            
            # Lists to store page numbers and their labels
            marked_pages: List[Tuple[int, str]] = []
            unmarked_pages: List[int] = []
            
            # Process each page
            for i, page in enumerate(doc):
                text = page.get_text()
                self.log_message(f"Processing page {i + 1}")
                
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
                            product_name = self.sku_map.get(sku, "Unknown Product")
                            # Only show quantity if it's greater than 1
                            label_text = f"→ {product_name}x{qty}" if qty > 1 else f"→ {product_name}"
                            sku_labels.append(label_text)
                
                if sku_labels:
                    # Concatenate all labels
                    label_text = " | ".join(sku_labels)
                    # Store the page number and its label
                    marked_pages.append((i, label_text))
                    self.log_message(f"Page {i + 1}: Found labels - {label_text}")
                else:
                    unmarked_pages.append(i)
                    self.log_message(f"Page {i + 1}: No labels found")
            
            self.log_message(f"Found {len(marked_pages)} marked pages and {len(unmarked_pages)} unmarked pages")
            
            # Create a new PDF with reordered pages
            new_doc = fitz.open()
            
            # Batch copy unmarked pages (more efficient)
            if unmarked_pages:
                self.log_message("Copying unmarked pages...")
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
            if marked_pages:
                self.log_message("Adding marked pages with labels...")
                for page_num, label_text in marked_pages:
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                    # Add label to the newly inserted page
                    insert_point = fitz.Point(5, 250)
                    new_doc[-1].insert_text(insert_point, label_text, 
                                           fontname="Courier-Bold", fontsize=12, color=(1, 0, 0))
            
            # Save with minimal optimization for speed
            self.log_message("Saving output file...")
            new_doc.save(output_path,
                         deflate=False,    # Disable compression for speed
                         garbage=1,        # Minimal garbage collection
                         clean=True)       # cleaning but slow
            
            self.log_message(f"Successfully saved to: {output_path}")
            
            # Close both documents
            doc.close()
            new_doc.close()
            
            # Update UI on main thread
            self.root.after(0, self._processing_complete, True, "Processing completed successfully!")
            
        except Exception as e:
            error_msg = f"Error during processing: {str(e)}"
            self.log_message(error_msg)
            self.root.after(0, self._processing_complete, False, error_msg)
            
    def _processing_complete(self, success, message):
        self.processing = False
        self.process_button.config(state="normal")
        self.progress.stop()
        
        if success:
            self.update_status("Processing completed successfully!")
            messagebox.showinfo("Success", f"PDF processed successfully!\nOutput saved to:\n{self.output_file_path.get()}")
        else:
            self.update_status("Processing failed")
            messagebox.showerror("Error", message)

def main():
    root = tk.Tk()
    app = PDFProcessorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 