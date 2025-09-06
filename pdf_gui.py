import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz  # PyMuPDF
import re
import os
from typing import List, Tuple, Dict
import threading
from collections import defaultdict

class WindowsStylePDFProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("Shiprocket Label Processor")
        self.root.geometry("1000x800")
        self.root.resizable(True, True)
        
        # Configure Windows-style theme
        self.setup_windows_theme()
        
        # Variables
        self.input_file_path = tk.StringVar()
        self.output_file_path = tk.StringVar()
        self.processing = False
        self.current_page = tk.StringVar(value="0")
        self.total_pages = tk.StringVar(value="0")
        
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
        
    def setup_windows_theme(self):
        """Configure Windows-native theme"""
        style = ttk.Style()
        
        # Use native Windows theme
        available_themes = style.theme_names()
        # print available_themes
        if 'vista' in available_themes:
            style.theme_use('vista')
        else:
            style.theme_use('clam')
        
        # Windows colors
        self.colors = {
            'bg_primary': '#f0f0f0',
            'bg_secondary': '#ffffff',
            'text_primary': '#000000',
            'text_secondary': '#666666',
            'accent': '#0078d4'
        }
        
        # Configure root window
        self.root.configure(bg=self.colors['bg_primary'])
        
    def setup_ui(self):
        # Main container with padding
        main_frame = tk.Frame(self.root, bg=self.colors['bg_primary'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=15)
        
        # Title section
        self.create_title_section(main_frame)
        
        # File selection section
        self.create_file_section(main_frame)
        
        # Control buttons section
        self.create_controls_section(main_frame)
        
        # Progress section
        self.create_progress_section(main_frame)
        
        # Statistics section
        self.create_stats_section(main_frame)
        
        # Log section
        self.create_log_section(main_frame)
        
    def create_title_section(self, parent):
        """Create title section"""
        title_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        title_frame.pack(fill='x', pady=(0, 20))
        
        title_label = tk.Label(title_frame, 
                              text="Shiprocket Label Processor",
                              font=('Segoe UI', 18, 'bold'),
                              bg=self.colors['bg_primary'],
                              fg=self.colors['text_primary'])
        title_label.pack(anchor='w')
        
        # subtitle_label = tk.Label(title_frame, 
        #                          text="Organize and process your shipping labels efficiently",
        #                          font=('Segoe UI', 9),
        #                          bg=self.colors['bg_primary'],
        #                          fg=self.colors['text_secondary'])
        # subtitle_label.pack(anchor='w', pady=(2, 0))
        
    def create_file_section(self, parent):
        """Create file selection section"""
        file_frame = ttk.LabelFrame(parent, text="File Selection", padding="15")
        file_frame.pack(fill='x', pady=(0, 15))
        
        # Input file row
        input_frame = tk.Frame(file_frame)
        input_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(input_frame, text="Input PDF:", 
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        input_entry_frame = tk.Frame(input_frame)
        input_entry_frame.pack(fill='x', pady=(5, 0))
        
        self.input_entry = ttk.Entry(input_entry_frame, 
                                    textvariable=self.input_file_path,
                                    font=('Segoe UI', 9),
                                    state='readonly')
        self.input_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ttk.Button(input_entry_frame, text="Browse...", 
                  command=self.browse_input_file).pack(side='right')
        
        # Output file row
        output_frame = tk.Frame(file_frame)
        output_frame.pack(fill='x')
        
        tk.Label(output_frame, text="Output PDF:", 
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        output_entry_frame = tk.Frame(output_frame)
        output_entry_frame.pack(fill='x', pady=(5, 0))
        
        self.output_entry = ttk.Entry(output_entry_frame, 
                                     textvariable=self.output_file_path,
                                     font=('Segoe UI', 9),
                                     state='readonly')
        self.output_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ttk.Button(output_entry_frame, text="Browse...", 
                  command=self.browse_output_file).pack(side='right')
        
    def create_controls_section(self, parent):
        """Create control buttons section"""
        controls_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        controls_frame.pack(fill='x', pady=(0, 15))
        
        # Primary action button
        self.process_button = ttk.Button(controls_frame, text="Process PDF", 
                                        command=self.process_pdf,
                                        width=50)
        self.process_button.pack(side='left')
        
        # Secondary actions
        self.open_pdf_button = ttk.Button(controls_frame, text="Print PDF", 
                                         command=self.open_converted_pdf,
                                         state='disabled',
                                         width=15)
        self.open_pdf_button.pack(side='left', padx=(10, 0))
        
        ttk.Button(controls_frame, text="Clear All", 
                  command=self.clear_all,
                  width=10).pack(side='left', padx=(10, 0))
        
    def create_progress_section(self, parent):
        """Create progress section"""
        progress_frame = ttk.LabelFrame(parent, text="Progress", padding="15")
        progress_frame.pack(fill='x', pady=(0, 15))
        
        # Status label
        self.status_label = tk.Label(progress_frame, text="Ready to process",
                                    font=('Segoe UI', 9, 'bold'),
                                    fg=self.colors['text_primary'])
        self.status_label.pack(anchor='w', pady=(0, 5))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill='x', pady=(0, 5))
        
        # Progress details
        self.progress_detail_label = tk.Label(progress_frame, text="",
                                             font=('Segoe UI', 8),
                                             fg=self.colors['text_secondary'])
        self.progress_detail_label.pack(anchor='w')
        
    def create_stats_section(self, parent):
        """Create statistics section"""
        self.stats_frame = ttk.LabelFrame(parent, text="Statistics", padding="15")
        self.stats_frame.pack(fill='x', pady=(0, 15))
        
        # Initially show placeholder
        self.stats_placeholder = tk.Label(self.stats_frame, 
                                         text="Statistics will appear here after processing",
                                         font=('Segoe UI', 9),
                                         fg=self.colors['text_secondary'])
        self.stats_placeholder.pack(pady=20)
        
    def create_log_section(self, parent):
        """Create log section"""
        log_frame = ttk.LabelFrame(parent, text="Processing Log", padding="10")
        log_frame.pack(fill='both', expand=True)
        
        # Log text area with scrollbar
        text_frame = tk.Frame(log_frame)
        text_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        # Text widget
        self.log_text = tk.Text(text_frame, height=8, wrap=tk.WORD,
                               font=('Consolas', 8),
                               bg='white', fg='black',
                               relief='sunken', borderwidth=1,
                               padx=8, pady=8)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, 
                                 command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Log controls
        log_controls = tk.Frame(log_frame)
        log_controls.pack(fill='x')
        
        ttk.Button(log_controls, text="Clear Log", 
                  command=self.clear_log).pack(side='left')
        
        ttk.Button(log_controls, text="Save Log", 
                  command=self.save_log).pack(side='left', padx=(10, 0))
        
    def display_statistics(self, oil_counts, potli_counts, marked_pages, unmarked_pages):
        """Display statistics in clean layout"""
        # Clear existing content
        for widget in self.stats_frame.winfo_children():
            if widget != self.stats_placeholder:
                widget.destroy()
        
        if hasattr(self, 'stats_placeholder'):
            self.stats_placeholder.destroy()
        
        # Create grid layout
        grid_frame = tk.Frame(self.stats_frame)
        grid_frame.pack(fill='x', padx=5, pady=5)
        
        # Configure grid columns
        grid_frame.columnconfigure(0, weight=1)
        grid_frame.columnconfigure(1, weight=1)
        grid_frame.columnconfigure(2, weight=1)
        
        # Pages column
        pages_frame = tk.Frame(grid_frame)
        pages_frame.grid(row=0, column=0, sticky='nw', padx=(0, 20))
        
        tk.Label(pages_frame, text="Pages", 
                font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        tk.Label(pages_frame, text=f"Marked: {len(marked_pages)}", 
                font=('Segoe UI', 9)).pack(anchor='w', pady=(2, 0))
        tk.Label(pages_frame, text=f"Unmarked: {len(unmarked_pages)}", 
                font=('Segoe UI', 9)).pack(anchor='w')
        
        # Oil column
        oil_frame = tk.Frame(grid_frame)
        oil_frame.grid(row=0, column=1, sticky='nw', padx=(0, 20))
        
        tk.Label(oil_frame, text="Oil Products", 
                font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        for qty, count in oil_counts.items():
            if count > 0:
                qty_text = f"{qty}x packs" if qty != 'more' else "4+ packs"
                tk.Label(oil_frame, text=f"{qty_text}: {count}", 
                        font=('Segoe UI', 9)).pack(anchor='w', pady=(2, 0))
        
        # Potli column
        potli_frame = tk.Frame(grid_frame)
        potli_frame.grid(row=0, column=2, sticky='nw')
        
        tk.Label(potli_frame, text="Potli Products", 
                font=('Segoe UI', 10, 'bold')).pack(anchor='w')
        for qty, count in potli_counts.items():
            if count > 0:
                qty_text = f"{qty}x packs" if qty != 'more' else "4+ packs"
                tk.Label(potli_frame, text=f"{qty_text}: {count}", 
                        font=('Segoe UI', 9)).pack(anchor='w', pady=(2, 0))
        
    def browse_input_file(self):
        filename = filedialog.askopenfilename(
            title="Select Input PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.input_file_path.set(filename)
            base_name = os.path.splitext(filename)[0]
            self.output_file_path.set(f"{base_name}_processed.pdf")
            self.log_message(f"Input file selected: {os.path.basename(filename)}")
            
    def browse_output_file(self):
        filename = filedialog.asksaveasfilename(
            title="Save Processed PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.output_file_path.set(filename)
            self.log_message(f"Output location set: {os.path.basename(filename)}")
            
    def clear_all(self):
        """Clear all inputs and reset UI"""
        self.input_file_path.set("")
        self.output_file_path.set("")
        self.clear_log()
        self.update_status("Ready to process")
        self.open_pdf_button.config(state="disabled")
        self.clear_statistics()
        
    def clear_statistics(self):
        """Clear statistics display"""
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        self.stats_placeholder = tk.Label(self.stats_frame, 
                                         text="Statistics will appear here after processing",
                                         font=('Segoe UI', 9),
                                         fg=self.colors['text_secondary'])
        self.stats_placeholder.pack(pady=20)
        
    def log_message(self, message):
        """Add message to log"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
        
    def save_log(self):
        """Save log to file"""
        filename = filedialog.asksaveasfilename(
            title="Save Log File",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                self.log_message(f"Log saved to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Could not save log: {e}")
        
    def update_status(self, message):
        """Update status label"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
        
    def update_progress_detail(self, current, total):
        """Update progress details"""
        self.progress_detail_label.config(text=f"{current}/{total} pages processed")
        
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
            
        # Start processing
        self.processing = True
        self.process_button.config(state="disabled", text="Processing...")
        self.progress_bar.start()
        self.update_status("Processing started...")
        self.clear_log()
        self.clear_statistics()
        
        thread = threading.Thread(target=self._process_pdf_thread, 
                                args=(input_path, output_path))
        thread.daemon = True
        thread.start()
    
    # Include all the optimized processing methods
    def extract_skus_from_page(self, lines: List[str]) -> List[Tuple[str, str]]:
        """Optimized SKU extraction using pre-compiled regex"""
        sku_labels = []
        i = 0
        lines_count = len(lines)
        
        while i < lines_count:
            line = lines[i]
            sku_match = self.sku_pattern.search(line)
            
            if sku_match and not sku_match.group(1).endswith('-'):
                sku = sku_match.group(1)
                qty = 1
                
                if i + 1 < lines_count:
                    qty_match = self.qty_pattern.search(lines[i + 1])
                    if qty_match:
                        qty = int(qty_match.group(1))
                
                product_name = self.sku_map.get(sku, "Unknown Product")
                label_text = f"→ {product_name}x{qty}" if qty > 1 else f"→ {product_name}"
                sku_labels.append((sku, label_text))
                i += 2
                
            elif "SKU:" in line and i + 1 < lines_count:
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
                i += 3
            else:
                i += 1
        
        return sku_labels
    
    def count_products(self, sku_labels: List[Tuple[str, str]]) -> Tuple[Dict, Dict]:
        """Optimized product counting"""
        oil_counts = defaultdict(int)
        potli_counts = defaultdict(int)
        
        for sku, label_text in sku_labels:
            product_name = self.sku_map.get(sku, "Unknown Product")
            
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
        """Handle special SKU logic"""
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
        """Optimized label sorting"""
        def get_priority(label: str) -> Tuple[int, str]:
            normalized = label.replace('→ ', '').replace(' ', '').upper()
            
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
        """Optimized page grouping"""
        marked_dict = dict(marked_pages)
        skipped_pages = set()
        
        for entries in skipped_special_skus.values():
            for entry in entries:
                skipped_pages.add(entry["page"])
        
        grouped_pairs = []
        used_pages = set()
        
        for page in unmarked_pages:
            next_page = page + 1
            if (next_page in marked_dict and 
                page not in skipped_pages and 
                next_page not in skipped_pages):
                grouped_pairs.append((page, next_page))
                used_pages.update([page, next_page])
        
        remaining_marked = [(i, label) for i, label in marked_pages if i not in used_pages]
        remaining_unmarked = [i for i in unmarked_pages if i not in used_pages]
        
        single_product_pages = []
        mixed_product_pages = []
        
        for i, label_text in remaining_marked:
            if " | " in label_text:
                mixed_product_pages.append((i, label_text))
            else:
                single_product_pages.append((i, label_text))
        
        page_groups = defaultdict(list)
        for i, label_text in single_product_pages:
            normalized_label = label_text.replace('→ ', '').replace(' ', '').upper()
            page_groups[normalized_label].append((i, label_text))
        
        final_order = []
        final_order.extend([(i, None) for i in remaining_unmarked])
        
        for group in self.group_order:
            labels_to_remove = []
            for label in sorted(page_groups.keys()):
                if label.startswith(group):
                    final_order.extend(page_groups[label])
                    labels_to_remove.append(label)
            for label in labels_to_remove:
                del page_groups[label]
        
        for label in sorted(page_groups.keys()):
            final_order.extend(page_groups[label])
        
        for no_sku, sku_page in grouped_pairs:
            final_order.extend([(no_sku, None), (sku_page, marked_dict[sku_page])])
        
        final_order.extend(mixed_product_pages)
        
        return final_order
        
    def _process_pdf_thread(self, input_path, output_path):
        try:
            self.log_message("Starting PDF processing...")
            
            doc = fitz.open(input_path)
            total_pages = len(doc)
            self.total_pages.set(str(total_pages))
            self.log_message(f"Opened PDF with {total_pages} pages")
            
            marked_pages = []
            unmarked_pages = []
            all_skipped_special_skus = defaultdict(list)
            total_oil_counts = defaultdict(int)
            total_potli_counts = defaultdict(int)
            
            self.log_message("Processing pages...")
            
            for i, page in enumerate(doc):
                self.current_page.set(str(i + 1))
                if i % 25 == 0 or i == total_pages - 1:
                    self.root.after(0, self.update_progress_detail, i + 1, total_pages)
                    self.log_message(f"Processing page {i+1}/{total_pages}")
                
                text = page.get_text()
                lines = text.splitlines()
                
                sku_labels = self.extract_skus_from_page(lines)
                
                if not sku_labels:
                    unmarked_pages.append(i)
                    continue
                
                oil_counts, potli_counts = self.count_products(sku_labels)
                for k, v in oil_counts.items():
                    total_oil_counts[k] += v
                for k, v in potli_counts.items():
                    total_potli_counts[k] += v
                
                final_labels, skipped_skus = self.process_special_skus(sku_labels, i)
                
                for sku_type, entries in skipped_skus.items():
                    all_skipped_special_skus[sku_type].extend(entries)
                
                if final_labels:
                    sorted_labels = self.sort_labels_optimized(final_labels)
                    label_text = " | ".join(sorted_labels)
                    marked_pages.append((i, label_text))
                else:
                    unmarked_pages.append(i)
            
            self.log_message(f"Found {len(marked_pages)} marked pages and {len(unmarked_pages)} unmarked pages")
            self.log_message(f"Oil counts: {dict(total_oil_counts)}")
            self.log_message(f"Potli counts: {dict(total_potli_counts)}")
            
            # Update statistics display
            self.root.after(0, self.display_statistics, dict(total_oil_counts), 
                          dict(total_potli_counts), marked_pages, unmarked_pages)
            
            self.log_message("Grouping and ordering pages...")
            final_page_order = self.group_pages_optimized(marked_pages, unmarked_pages, all_skipped_special_skus)
            
            self.log_message("Creating new PDF with reordered pages...")
            new_doc = fitz.open()
            
            ordered_pages = [i for i, _ in final_page_order]
            label_dict = {i: label for i, label in final_page_order if label is not None}
            
            batch_size = 50
            total_batches = (len(ordered_pages) - 1) // batch_size + 1
            
            for batch_num, batch_start in enumerate(range(0, len(ordered_pages), batch_size)):
                batch_end = min(batch_start + batch_size, len(ordered_pages))
                batch_pages = ordered_pages[batch_start:batch_end]
                
                self.log_message(f"Processing batch {batch_num + 1}/{total_batches}")
                
                for page_num in batch_pages:
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                    
                    if page_num in label_dict:
                        insert_point = fitz.Point(5, 250)
                        new_doc[-1].insert_text(insert_point, label_dict[page_num], 
                                               fontname="Courier-Bold", fontsize=12, color=(0, 0, 0))
            
            self.log_message("Saving output file...")
            new_doc.save(output_path,
                         deflate=False,
                         garbage=1,
                         clean=True)
            
            self.log_message(f"Successfully saved to: {os.path.basename(output_path)}")
            
            doc.close()
            new_doc.close()
            
            self.root.after(0, self._processing_complete, True, "Processing completed successfully!")
            
        except Exception as e:
            error_msg = f"Error during processing: {str(e)}"
            self.log_message(error_msg)
            self.root.after(0, self._processing_complete, False, error_msg)
            
    def _processing_complete(self, success, message):
        self.processing = False
        self.process_button.config(state="normal", text="Process PDF")
        self.progress_bar.stop()
        self.progress_detail_label.config(text="")
        
        if success:
            self.update_status("Processing completed successfully!")
            messagebox.showinfo("Success", f"PDF processed successfully!\n\nOutput saved to:\n{self.output_file_path.get()}")
            self.open_pdf_button.config(state="normal")
            self.log_message("Ready for next processing task")
        else:
            self.update_status("Processing failed")
            messagebox.showerror("Error", message)
            self.open_pdf_button.config(state="disabled")
            
    def open_converted_pdf(self):
        output_path = self.output_file_path.get()
        if output_path and os.path.exists(output_path):
            try:
                os.startfile(output_path)
                self.log_message("Opening converted PDF...")
            except Exception as e:
                error_msg = f"Could not open PDF: {e}"
                messagebox.showerror("Error", error_msg)
                self.log_message(error_msg)
        else:
            error_msg = "Converted PDF not found."
            messagebox.showerror("Error", error_msg)
            self.log_message(error_msg)

def main():
    root = tk.Tk()
    app = WindowsStylePDFProcessor(root)
    root.mainloop()

if __name__ == "__main__":
    main()