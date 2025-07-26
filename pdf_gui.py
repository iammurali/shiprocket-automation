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
        self.root.geometry("600x600")
        self.root.resizable(True, True)
        
        # Variables
        self.input_file_path = tk.StringVar()
        self.output_file_path = tk.StringVar()
        self.processing = False
        
        # SKU to product name mapping
        self.sku_map = {
            "TN0001": "OIL",
            "TN0002": "Potli", 
            "TN003": "Rollon",
            "TS-NLT5-CZ47": "OIL",
            "84-HNM4-WOND": "Potli",
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
        # Open PDF button (initially disabled)
        self.open_pdf_button = ttk.Button(main_frame, text="Open Converted PDF", command=self.open_converted_pdf, state="disabled")
        self.open_pdf_button.grid(row=7, column=0, columnspan=3, pady=(10, 0))
        
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
            # Dict to track skipped TN0001 and TS-NLT5-CZ47
            skipped_special_skus = {"TN0001": [], "TS-NLT5-CZ47": []}
            
            # Stats counters
            oil_counts = {1: 0, 2: 0, 3: 0, 'more': 0}
            potli_counts = {1: 0, 2: 0, 3: 0, 'more': 0}
            
            # Process each page
            for i, page in enumerate(doc):
                text = page.get_text()
                # Find all SKUs and their quantities
                lines = text.splitlines()
                sku_labels = []
                for idx, line in enumerate(lines):
                    sku = None
                    qty = 1
                    # Try to match SKU on one line
                    sku_match = re.search(r'SKU:\s*([\w\-]+)', line)
                    if sku_match and not sku_match.group(1).endswith('-'):
                        sku = sku_match.group(1)
                        # Try to get the next line for quantity
                        if idx + 1 < len(lines):
                            next_line = lines[idx + 1]
                            qty_match = re.search(r'(\d+)', next_line)
                            if qty_match:
                                qty = int(qty_match.group(1))
                        product_name = self.sku_map.get(sku, "Unknown Product")
                        label_text = f"→ {product_name}x{qty}" if qty > 1 else f"→ {product_name}"
                        sku_labels.append((sku, label_text))
                        # Count stats for OIL and Potli
                        if product_name == "OIL":
                            if qty == 1:
                                oil_counts[1] += 1
                            elif qty == 2:
                                oil_counts[2] += 1
                            elif qty == 3:
                                oil_counts[3] += 1
                            elif qty > 3:
                                oil_counts['more'] += 1
                        elif product_name == "Potli":
                            if qty == 1:
                                potli_counts[1] += 1
                            elif qty == 2:
                                potli_counts[2] += 1
                            elif qty == 3:
                                potli_counts[3] += 1
                            elif qty > 3:
                                potli_counts['more'] += 1
                    # Try to match SKU split across two lines (e.g. 'SKU: TS-NLT5-' and 'CZ47')
                    elif "SKU:" in line:
                        sku_prefix = line.strip().replace("SKU:", "").strip()
                        sku_suffix = lines[idx + 1].strip()
                        # Always ensure dash between prefix and suffix if not present
                        if sku_prefix and sku_suffix and not sku_prefix.endswith("-") and not sku_suffix.startswith("-"):
                            sku_full = sku_prefix + "-" + sku_suffix
                        else:
                            sku_full = sku_prefix + sku_suffix
                        sku_full = sku_full.replace(" ", "")
                        sku = sku_full
                        # Quantity will be on the third line
                        if idx + 2 < len(lines):
                            qty_line = lines[idx + 2]
                            qty_match = re.search(r'(\d+)', qty_line)
                            if qty_match:
                                qty = int(qty_match.group(1))
                        product_name = self.sku_map.get(sku, "Unknown Product")
                        label_text = f"→ {product_name}x{qty}" if qty > 1 else f"→ {product_name}"
                        sku_labels.append((sku, label_text))
                        # Count stats for OIL and Potli
                        if product_name == "OIL":
                            if qty == 1:
                                oil_counts[1] += 1
                            elif qty == 2:
                                oil_counts[2] += 1
                            elif qty == 3:
                                oil_counts[3] += 1
                            elif qty > 3:
                                oil_counts['more'] += 1
                        elif product_name == "Potli":
                            if qty == 1:
                                potli_counts[1] += 1
                            elif qty == 2:
                                potli_counts[2] += 1
                            elif qty == 3:
                                potli_counts[3] += 1
                            elif qty > 3:
                                potli_counts['more'] += 1
                # Post-process sku_labels for TN0001 logic
                final_labels = []
                skus_on_page = [sku for sku, _ in sku_labels]
                for idx, (sku, label_text) in enumerate(sku_labels):
                    if sku == "TN0001":
                        # Add TN0001 if qty > 1, or if there is another SKU on the page
                        if "x" in label_text or len(skus_on_page) > 1:
                            final_labels.append(label_text)
                        else:
                            skipped_special_skus["TN0001"].append({"page": i, "qty": 1, "skus_on_page": skus_on_page})
                    elif sku == "TS-NLT5-CZ47":
                        # Only add TS-NLT5-CZ47 if qty > 1
                        if "x" in label_text:
                            final_labels.append(label_text)
                        else:
                            skipped_special_skus["TS-NLT5-CZ47"].append({"page": i, "qty": 1, "skus_on_page": skus_on_page})
                    else:
                        final_labels.append(label_text)

                if final_labels:
                    label_text = " | ".join(final_labels)
                    marked_pages.append((i, label_text))
                else:
                    unmarked_pages.append(i)
            self.log_message(f"Found {len(marked_pages)} marked pages and {len(unmarked_pages)} unmarked pages")
            self.log_message(f"OIL counts: 1x={oil_counts[1]}, 2x={oil_counts[2]}, 3x={oil_counts[3]}, morex={oil_counts['more']}")
            self.log_message(f"Potli counts: 1x={potli_counts[1]}, 2x={potli_counts[2]}, 3x={potli_counts[3]}, morex={potli_counts['more']}")

            # Group no-SKU page and its following SKU page together at the end
            marked_dict = dict(marked_pages)
            grouped_pairs = []
            used_pages = set()
            i = 0
            def is_skipped(page_num):
                for entry in skipped_special_skus["TN0001"] + skipped_special_skus["TS-NLT5-CZ47"]:
                    if entry["page"] == page_num:
                        return True
                return False
            while i < len(unmarked_pages):
                page = unmarked_pages[i]
                # Only group if neither page nor next page are in skipped_special_skus
                if (page + 1) in marked_dict and not is_skipped(page) and not is_skipped(page + 1):
                    # Group no-SKU page and its following SKU page
                    grouped_pairs.append((page, page + 1))
                    used_pages.add(page)
                    used_pages.add(page + 1)
                    i += 1  # skip next page as it's already grouped
                i += 1
            # Collect all marked pages not in grouped pairs
            remaining_marked = [(i, label_text) for i, label_text in marked_pages if i not in used_pages]
            # Collect all unmarked pages not in grouped pairs
            remaining_unmarked = [i for i in unmarked_pages if i not in used_pages]

            # Prepare final page order: unmarked pages at top, then all marked and grouped pairs at the bottom
            final_page_order = []
            # Add all remaining unmarked pages first
            for i in remaining_unmarked:
                final_page_order.append((i, None))
            # Add all marked pages and grouped pairs at the bottom
            marked_and_grouped = []
            for i, label_text in remaining_marked:
                marked_and_grouped.append((i, label_text))
            for no_sku, sku_page in grouped_pairs:
                marked_and_grouped.append((no_sku, None))
                marked_and_grouped.append((sku_page, marked_dict[sku_page]))
            final_page_order.extend(marked_and_grouped)

            # For PDF creation, keep track of all pages in order, and which ones get labels
            ordered_pages = [i for i, _ in final_page_order]
            label_dict = {i: label_text for i, label_text in final_page_order if label_text is not None}

            # Create a new PDF with reordered pages
            new_doc = fitz.open()
            
            # Copy all pages in the new order, adding labels only to marked pages
            self.log_message("Copying pages in new grouped order...Please Wait.. this will take some time")
            for page_num in ordered_pages:
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                if page_num in label_dict:
                    # Add label to the newly inserted page
                    insert_point = fitz.Point(5, 250)
                    new_doc[-1].insert_text(insert_point, label_dict[page_num], 
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
            self.open_pdf_button.config(state="normal")
        else:
            self.update_status("Processing failed")
            messagebox.showerror("Error", message)
            self.open_pdf_button.config(state="disabled")
            
    def open_converted_pdf(self):
        output_path = self.output_file_path.get()
        if output_path and os.path.exists(output_path):
            try:
                os.startfile(output_path)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open PDF: {e}")
        else:
            messagebox.showerror("Error", "Converted PDF not found.")

def main():
    root = tk.Tk()
    app = PDFProcessorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()