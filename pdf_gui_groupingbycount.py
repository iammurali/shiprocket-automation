import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz  # PyMuPDF
import re
import os
from typing import List, Tuple, Dict
import threading
from collections import defaultdict

class PDFProcessorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Shiprocket Label Processor")
        self.root.geometry("650x650")
        self.root.resizable(True, True)
        
        # Variables
        self.input_file_path = tk.StringVar()
        self.output_file_path = tk.StringVar()
        self.processing = False
        
        # SKU to product name mapping
        self.sku_map = {
            "TN0001": "OIL",
            "TS-NLT5-CZ47": "OIL",
            "TN0002": "Potli", 
            "84-HNM4-WOND": "Potli",
            "TN003": "Rollon",
        }
        
        # Pre-compile regex patterns for better performance
        self.sku_pattern = re.compile(r'SKU:\s*([\w\-]+)', re.IGNORECASE)
        self.qty_pattern = re.compile(r'(\d+)')
        
        # Define group order as class variable for reuse
        self.group_order = [
            'OIL', 'OILX2', 'OILX3', 'OILX4',
            'POTLI', 'POTLIX2', 'POTLIX3', 'POTLIX4',
            'ROLLON', 'ROLLONX2', 'ROLLONX3', 'ROLLONX4'
        ]
        
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
        title_label = ttk.Label(main_frame, text="Shiprocket Label Processor", 
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
        self.process_button.grid(row=3, column=0, columnspan=2, pady=20, sticky=(tk.W, tk.E))
        # Open PDF button
        self.open_pdf_button = ttk.Button(main_frame, text="PRINT Converted PDF", 
                                         command=self.open_converted_pdf, state="disabled")
        self.open_pdf_button.grid(row=3, column=2, pady=20, sticky=(tk.W, tk.E))
        
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
    
    def extract_skus_from_page(self, lines: List[str]) -> List[Tuple[str, str]]:
        """Optimized SKU extraction using pre-compiled regex and vectorized operations"""
        sku_labels = []
        i = 0
        lines_count = len(lines)
        
        while i < lines_count:
            line = lines[i]
            sku_match = self.sku_pattern.search(line)
            
            if sku_match and not sku_match.group(1).endswith('-'):
                # Single-line SKU
                sku = sku_match.group(1)
                qty = 1
                
                if i + 1 < lines_count:
                    qty_match = self.qty_pattern.search(lines[i + 1])
                    if qty_match:
                        qty = int(qty_match.group(1))
                
                product_name = self.sku_map.get(sku, "Unknown Product")
                label_text = f"→ {product_name}x{qty}" if qty > 1 else f"→ {product_name}"
                sku_labels.append((sku, label_text))
                i += 2  # Skip next line as it was checked for quantity
                
            elif "SKU:" in line and i + 1 < lines_count:
                # Multi-line SKU
                sku_prefix = line.replace("SKU:", "").strip()
                sku_suffix = lines[i + 1].strip()
                
                if sku_prefix and sku_suffix and not sku_prefix.endswith("-") and not sku_suffix.startswith("-"):
                    sku_full = f"{sku_prefix}-{sku_suffix}"
                else:
                    sku_full = sku_prefix + sku_suffix
                
                sku = sku_full.replace(" ", "")
                qty = 1
                
                if i + 2 < lines_count:
                    qty_match = self.qty_pattern.search(lines[i + 2])
                    if qty_match:
                        qty = int(qty_match.group(1))
                
                product_name = self.sku_map.get(sku, "Unknown Product")
                label_text = f"→ {product_name}x{qty}" if qty > 1 else f"→ {product_name}"
                sku_labels.append((sku, label_text))
                i += 3  # Skip the next two lines
            else:
                i += 1
        
        return sku_labels
    
    def count_products(self, sku_labels: List[Tuple[str, str]]) -> Tuple[Dict, Dict]:
        """Optimized product counting using defaultdict"""
        oil_counts = defaultdict(int)
        potli_counts = defaultdict(int)
        
        for sku, label_text in sku_labels:
            product_name = self.sku_map.get(sku, "Unknown Product")
            
            # Extract quantity from label
            if "x" in label_text:
                qty = int(label_text.split("x")[1])
            else:
                qty = 1
            
            if product_name == "OIL":
                if qty <= 3:
                    oil_counts[qty] += 1
                else:
                    oil_counts['more'] += 1
            elif product_name == "Potli":
                if qty <= 3:
                    potli_counts[qty] += 1
                else:
                    potli_counts['more'] += 1
        
        return dict(oil_counts), dict(potli_counts)
    
    def process_special_skus(self, sku_labels: List[Tuple[str, str]], page_num: int) -> Tuple[List[str], Dict]:
        """Handle special SKU logic efficiently"""
        final_labels = []
        skipped_special_skus = defaultdict(list)
        skus_on_page = [sku for sku, _ in sku_labels]
        
        for sku, label_text in sku_labels:
            if sku == "TN0001":
                if "x" in label_text or len(skus_on_page) > 1:
                    final_labels.append(label_text)
                else:
                    skipped_special_skus["TN0001"].append({
                        "page": page_num, "qty": 1, "skus_on_page": skus_on_page
                    })
            elif sku == "TS-NLT5-CZ47":
                if "x" in label_text:
                    final_labels.append(label_text)
                else:
                    skipped_special_skus["TS-NLT5-CZ47"].append({
                        "page": page_num, "qty": 1, "skus_on_page": skus_on_page
                    })
            else:
                final_labels.append(label_text)
        
        return final_labels, dict(skipped_special_skus)
    
    def sort_labels_optimized(self, labels: List[str]) -> List[str]:
        """Optimized label sorting with cached priority mapping"""
        def get_priority(label: str) -> Tuple[int, str]:
            normalized = label.replace('→ ', '').replace(' ', '').upper()
            
            # Use string matching for better performance
            if normalized == 'OIL':
                return (1, normalized)
            elif normalized.startswith('OILX2'):
                return (2, normalized)
            elif normalized.startswith('OILX3'):
                return (3, normalized)
            elif normalized.startswith('OILX'):
                return (4, normalized)
            elif normalized == 'POTLI':
                return (5, normalized)
            elif normalized.startswith('POTLIX2'):
                return (6, normalized)
            elif normalized.startswith('POTLIX3'):
                return (7, normalized)
            elif normalized.startswith('POTLIX'):
                return (8, normalized)
            elif normalized == 'ROLLON':
                return (9, normalized)
            elif normalized.startswith('ROLLONX2'):
                return (10, normalized)
            elif normalized.startswith('ROLLONX'):
                return (11, normalized)
            else:
                return (99, normalized)
        
        return sorted(labels, key=get_priority)
    
    def group_pages_optimized(self, marked_pages: List[Tuple[int, str]], 
                            unmarked_pages: List[int], 
                            skipped_special_skus: Dict) -> List[Tuple[int, str]]:
        """Optimized page grouping with better data structures"""
        marked_dict = dict(marked_pages)
        skipped_pages = set()
        
        # Create set of skipped pages for O(1) lookup
        for entries in skipped_special_skus.values():
            for entry in entries:
                skipped_pages.add(entry["page"])
        
        # Group consecutive unmarked-marked pairs
        grouped_pairs = []
        used_pages = set()
        
        for page in unmarked_pages:
            next_page = page + 1
            if (next_page in marked_dict and 
                page not in skipped_pages and 
                next_page not in skipped_pages):
                grouped_pairs.append((page, next_page))
                used_pages.update([page, next_page])
        
        # Separate remaining pages
        remaining_marked = [(i, label) for i, label in marked_pages if i not in used_pages]
        remaining_unmarked = [i for i in unmarked_pages if i not in used_pages]
        
        # Group marked pages by product type
        single_product_pages = []
        mixed_product_pages = []
        
        for i, label_text in remaining_marked:
            if " | " in label_text:
                mixed_product_pages.append((i, label_text))
            else:
                single_product_pages.append((i, label_text))
        
        # Group single product pages efficiently
        page_groups = defaultdict(list)
        for i, label_text in single_product_pages:
            normalized_label = label_text.replace('→ ', '').replace(' ', '').upper()
            page_groups[normalized_label].append((i, label_text))
        
        # Build final order
        final_order = []
        
        # Add unmarked pages first
        final_order.extend([(i, None) for i in remaining_unmarked])
        
        # Add grouped single product pages
        for group in self.group_order:
            for label in sorted(page_groups.keys()):
                if label.startswith(group):
                    final_order.extend(page_groups[label])
                    del page_groups[label]  # Remove processed group
        
        # Add remaining single product groups
        for label in sorted(page_groups.keys()):
            final_order.extend(page_groups[label])
        
        # Add grouped pairs
        for no_sku, sku_page in grouped_pairs:
            final_order.extend([(no_sku, None), (sku_page, marked_dict[sku_page])])
        
        # Add mixed product pages at the end
        final_order.extend(mixed_product_pages)
        
        return final_order
        
    def _process_pdf_thread(self, input_path, output_path):
        try:
            self.log_message("Starting PDF processing...")
            
            # Open the original PDF
            doc = fitz.open(input_path)
            self.log_message(f"Opened PDF with {len(doc)} pages")
            
            # Initialize tracking variables
            marked_pages = []
            unmarked_pages = []
            all_skipped_special_skus = defaultdict(list)
            total_oil_counts = defaultdict(int)
            total_potli_counts = defaultdict(int)
            
            # Process pages in batches for better memory usage
            self.log_message("Processing pages...")
            
            for i, page in enumerate(doc):
                # Update progress periodically
                if i % 50 == 0:
                    self.log_message(f"Processing page {i+1}/{len(doc)}...")
                
                text = page.get_text()
                lines = text.splitlines()
                
                # Extract SKUs efficiently
                sku_labels = self.extract_skus_from_page(lines)
                
                if not sku_labels:
                    unmarked_pages.append(i)
                    continue
                
                # Count products
                oil_counts, potli_counts = self.count_products(sku_labels)
                for k, v in oil_counts.items():
                    total_oil_counts[k] += v
                for k, v in potli_counts.items():
                    total_potli_counts[k] += v
                
                # Process special SKUs
                final_labels, skipped_skus = self.process_special_skus(sku_labels, i)
                
                # Merge skipped SKUs
                for sku_type, entries in skipped_skus.items():
                    all_skipped_special_skus[sku_type].extend(entries)
                
                if final_labels:
                    # Sort and join labels
                    sorted_labels = self.sort_labels_optimized(final_labels)
                    label_text = " | ".join(sorted_labels)
                    marked_pages.append((i, label_text))
                else:
                    unmarked_pages.append(i)
            
            self.log_message(f"Found {len(marked_pages)} marked pages and {len(unmarked_pages)} unmarked pages")
            self.log_message(f"OIL counts: {dict(total_oil_counts)}")
            self.log_message(f"Potli counts: {dict(total_potli_counts)}")
            
            # Group pages efficiently
            self.log_message("Grouping and ordering pages...")
            final_page_order = self.group_pages_optimized(marked_pages, unmarked_pages, all_skipped_special_skus)
            
            # Create new PDF with optimized copying
            self.log_message("Creating new PDF with reordered pages...")
            new_doc = fitz.open()
            
            # Extract page order and labels for efficient processing
            ordered_pages = [i for i, _ in final_page_order]
            label_dict = {i: label for i, label in final_page_order if label is not None}
            
            # Batch copy pages for better performance
            batch_size = 100
            for batch_start in range(0, len(ordered_pages), batch_size):
                batch_end = min(batch_start + batch_size, len(ordered_pages))
                batch_pages = ordered_pages[batch_start:batch_end]
                
                self.log_message(f"Processing batch {batch_start//batch_size + 1}/{(len(ordered_pages)-1)//batch_size + 1}...")
                
                for page_num in batch_pages:
                    # Copy page
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                    
                    # Add label if needed
                    if page_num in label_dict:
                        insert_point = fitz.Point(5, 250)
                        new_doc[-1].insert_text(insert_point, label_dict[page_num], 
                                               fontname="Courier-Bold", fontsize=12, color=(0, 0, 0))
            
            # Save with optimized settings
            self.log_message("Saving output file...")
            new_doc.save(output_path,
                         deflate=False,    # Disable compression for speed
                         garbage=1,        # Minimal garbage collection
                         clean=True)      # Skip cleaning for speed
            
            self.log_message(f"Successfully saved to: {output_path}")
            
            # Close documents
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