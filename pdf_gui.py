import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import fitz  # PyMuPDF
import re
import os
import sys
from typing import List, Tuple, Dict
import requests
import json
import threading
from collections import defaultdict
import datetime
import random
import webbrowser

class WindowsStylePDFProcessor:
    def __init__(self, root):
        self.root = root
        self.root.title("Shiprocket Label Processor")
        self.root.geometry("1000x800")
        self.root.resizable(True, True)
        
        self.config_file = "config.json"
        self.shiprocket_config = self.load_config()
        
        # Configure Windows-style theme
        self.setup_windows_theme()
        
        # Variables
        self.input_file_path = tk.StringVar()
        self.output_file_path = tk.StringVar()
        self.default_output_dir = tk.StringVar(value=self.get_default_output_dir("label_processor"))
        self.st_default_output_dir = tk.StringVar(value=self.get_default_output_dir("st_courier"))
        self.delhivery_default_output_dir = tk.StringVar(value=self.get_default_output_dir("delhivery_direct"))
        # Toggle for 4x4 label (crop bottom 50mm)
        self.is_4x4_var = tk.BooleanVar(value=False)
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
            "43522344878158": "Varico",
            "TN0005": "Varico"
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

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"email": "", "password": "", "token": "", "shopify_url": "", "shopify_token": ""}

    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.shiprocket_config, f)

    def get_default_output_dir(self, tab_name):
        """Return and create a tab-specific default output folder under Documents."""
        documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
        output_dir = os.path.join(documents_dir, "Shiprocket Label Processor", tab_name)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def browse_default_output_folder(self, folder_var):
        """Open a folder picker and save the chosen folder to the provided StringVar."""
        folder_path = filedialog.askdirectory(
            title="Select Default Output Folder",
            initialdir=folder_var.get() or os.path.join(os.path.expanduser("~"), "Documents")
        )
        if folder_path:
            folder_var.set(folder_path)

    def set_default_output_path(self, source_path, output_var, folder_var, fallback_dir_name, suffix):
        """Set the output file path using the chosen per-tab default folder."""
        output_dir = folder_var.get().strip() if folder_var.get() else ""
        if not output_dir or not os.path.isdir(output_dir):
            output_dir = self.get_default_output_dir(fallback_dir_name)
        os.makedirs(output_dir, exist_ok=True)
        folder_var.set(output_dir)

        base_name = os.path.splitext(os.path.basename(source_path))[0]
        output_var.set(os.path.join(output_dir, f"{base_name}{suffix}.pdf"))

    def setup_windows_theme(self):
        """Configure Windows-native theme"""
        style = ttk.Style()
        
        # Use native Windows theme
        available_themes = style.theme_names()
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
        # Create Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tab 1: Label Processor (Existing)
        self.processor_tab = tk.Frame(self.notebook, bg=self.colors['bg_primary'])
        self.notebook.add(self.processor_tab, text='Label Processor')

        # Main container for Label Processor
        main_frame = tk.Frame(self.processor_tab, bg=self.colors['bg_primary'])
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
        
        # Tab 2: COUTIER PDF Generator (New)
        self.courier_tab = tk.Frame(self.notebook, bg=self.colors['bg_primary'])
        self.notebook.add(self.courier_tab, text='COURIER PDF Generator')
        
        self.courier_orders = []
        self.courier_4x4_var = tk.BooleanVar(value=False)
        self.setup_courier_ui(self.courier_tab)

        # Tab 3: ST COURIER LABELS (separate processor)
        self.st_courier_tab = tk.Frame(self.notebook, bg=self.colors['bg_primary'])
        self.notebook.add(self.st_courier_tab, text='ST COURIER LABELS')

        self.setup_st_courier_ui(self.st_courier_tab)

        # Tab 4: DELHIVERY DIRECT LABELS
        self.delhivery_tab = tk.Frame(self.notebook, bg=self.colors['bg_primary'])
        self.notebook.add(self.delhivery_tab, text='DELHIVERY DIRECT')

        self.setup_delhivery_ui(self.delhivery_tab)

    def setup_courier_ui(self, parent):
        """Create UI for Courier PDF Generator"""
        # Top frame for Inputs
        input_frame = ttk.LabelFrame(parent, text="Add New Order", padding="15")
        input_frame.pack(fill='x', padx=20, pady=15)
        
        # Grid layout for inputs
        grid = tk.Frame(input_frame)
        grid.pack(fill='x')
        
        # Order ID
        tk.Label(grid, text="Order ID:", font=('Segoe UI', 9, 'bold')).grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.c_order_id = ttk.Entry(grid, width=20)
        self.c_order_id.grid(row=0, column=1, sticky='w', padx=5, pady=5)
        
        # Fetch Button
        fetch_btn = ttk.Button(grid, text="Fetch Info", command=self.fetch_shiprocket_details, width=10)
        fetch_btn.grid(row=0, column=2, sticky='w', padx=5, pady=5)

        # Phone
        tk.Label(grid, text="Phone:", font=('Segoe UI', 9, 'bold')).grid(row=0, column=3, sticky='w', padx=5, pady=5)
        self.c_phone = ttk.Entry(grid, width=20)
        self.c_phone.grid(row=0, column=4, sticky='w', padx=5, pady=5)
        
        # Fetch Button (Phone) - Removed as per user request
        # fetch_phone_btn = ttk.Button(grid, text="Fetch Info", command=self.fetch_shiprocket_by_phone, width=10)
        # fetch_phone_btn.grid(row=0, column=5, sticky='w', padx=5, pady=5)
        
        # Items
        tk.Label(grid, text="Items & Qty:", font=('Segoe UI', 9, 'bold')).grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.c_items = ttk.Entry(grid, width=50)
        self.c_items.grid(row=1, column=1, columnspan=5, sticky='we', padx=5, pady=5)
        
        # Address
        tk.Label(grid, text="Address:", font=('Segoe UI', 9, 'bold')).grid(row=2, column=0, sticky='nw', padx=5, pady=5)
        self.c_address = tk.Text(grid, height=4, width=50, font=('Segoe UI', 9))
        self.c_address.grid(row=2, column=1, columnspan=5, sticky='we', padx=5, pady=5)
        
        # Buttons
        btn_frame = tk.Frame(input_frame)
        btn_frame.pack(fill='x', pady=10)
        
        ttk.Button(btn_frame, text="Settings", command=self.open_settings).pack(side='left')
        ttk.Button(btn_frame, text="Add to Queue", command=self.add_courier_order).pack(side='right')
        
        # Middle frame for List
        list_frame = ttk.LabelFrame(parent, text="Order Queue", padding="15")
        list_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))
        
        # Treeview
        columns = ('order_id', 'phone', 'items', 'address')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings')
        self.tree.heading('order_id', text='Order ID')
        self.tree.heading('phone', text='Phone')
        self.tree.heading('items', text='Items')
        self.tree.heading('address', text='Address')
        
        self.tree.column('order_id', width=100)
        self.tree.column('phone', width=100)
        self.tree.column('items', width=200)
        self.tree.column('address', width=300)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Bottom frame for Actions
        action_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        action_frame.pack(fill='x', padx=20, pady=(0, 20))
        
        ttk.Button(action_frame, text="Remove Selected", command=self.delete_courier_order).pack(side='left')
        ttk.Button(action_frame, text="Update Shopify", command=self.update_shopify_comments).pack(side='left', padx=(10, 0))
        ttk.Button(action_frame, text="Generate Labels PDF", command=self.generate_courier_labels).pack(side='right')
        
        # 4x4 Checkbox
        ttk.Checkbutton(action_frame, text="4x4 Label", variable=self.courier_4x4_var).pack(side='right', padx=(0, 10))

    def update_shopify_comments(self):
        url = self.shiprocket_config.get("shopify_url")
        token = self.shiprocket_config.get("shopify_token")
        
        if not url or not token:
            messagebox.showerror("Configuration Error", "Please configure Shopify Store URL and Access Token in Settings.")
            self.open_settings()
            return
            
        if not self.courier_orders:
            messagebox.showinfo("Empty Queue", "No orders to update.")
            return

        # Ensure URL is formatted correctly (https://shop.myshopify.com)
        if not url.startswith("http"):
            url = f"https://{url}"
        
        # Remove trailing slash
        url = url.rstrip("/")

        success_count = 0
        fail_count = 0
        
        # Run in thread to prevent freezing
        threading.Thread(target=self._process_shopify_updates, args=(url, token)).start()

    # ---- ST COURIER LABELS UI and handlers ----
    def setup_st_courier_ui(self, parent):
        """Create UI for ST COURIER LABELS with PDF file selection"""
        # Variables for ST tab
        self.st_input_file_path = tk.StringVar()
        self.st_output_file_path = tk.StringVar()
        
        # Main container
        main_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=15)
        
        # Title section
        title_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        title_frame.pack(fill='x', pady=(0, 20))
        
        title_label = tk.Label(title_frame, 
                              text="ST Courier Label Processor",
                              font=('Segoe UI', 18, 'bold'),
                              bg=self.colors['bg_primary'],
                              fg=self.colors['text_primary'])
        title_label.pack(anchor='w')
        
        # File selection section
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="15")
        file_frame.pack(fill='x', pady=(0, 15))
        
        # Input file row
        input_frame = tk.Frame(file_frame)
        input_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(input_frame, text="Input PDF:", 
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        input_entry_frame = tk.Frame(input_frame)
        input_entry_frame.pack(fill='x', pady=(5, 0))
        
        self.st_input_entry = ttk.Entry(input_entry_frame, 
                                       textvariable=self.st_input_file_path,
                                       font=('Segoe UI', 9),
                                       state='readonly')
        self.st_input_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ttk.Button(input_entry_frame, text="Browse...", 
                  command=self.browse_st_input_file).pack(side='right')
        
        # Output file row
        output_frame = tk.Frame(file_frame)
        output_frame.pack(fill='x')
        
        tk.Label(output_frame, text="Output PDF:", 
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        output_entry_frame = tk.Frame(output_frame)
        output_entry_frame.pack(fill='x', pady=(5, 0))
        
        self.st_output_entry = ttk.Entry(output_entry_frame, 
                                        textvariable=self.st_output_file_path,
                                        font=('Segoe UI', 9),
                                        state='readonly')
        self.st_output_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ttk.Button(output_entry_frame, text="Browse...", 
                  command=self.browse_st_output_file).pack(side='right')

        default_folder_frame = tk.Frame(file_frame)
        default_folder_frame.pack(fill='x', pady=(10, 0))

        tk.Label(default_folder_frame, text="Default Output Folder:",
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        default_folder_entry_frame = tk.Frame(default_folder_frame)
        default_folder_entry_frame.pack(fill='x', pady=(5, 0))

        self.st_default_output_dir_entry = ttk.Entry(default_folder_entry_frame,
                                                     textvariable=self.st_default_output_dir,
                                                     font=('Segoe UI', 9),
                                                     state='readonly')
        self.st_default_output_dir_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ttk.Button(default_folder_entry_frame, text="Browse Folder",
                  command=lambda: self.browse_default_output_folder(self.st_default_output_dir)).pack(side='right')
        
        # Control buttons section
        controls_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        controls_frame.pack(fill='x', pady=(0, 15))
        
        self.st_process_button = ttk.Button(controls_frame, text="Process PDF", 
                                           command=self.process_st_pdf)
        self.st_process_button.pack(side='left', padx=(0, 10))
        
        self.st_open_pdf_button = ttk.Button(controls_frame, text="Print PDF", 
                                            command=self.open_st_converted_pdf,
                                            state='disabled')
        self.st_open_pdf_button.pack(side='left', padx=(10, 0))
        
        # Progress section (minimal)
        prog_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        prog_frame.pack(fill='x', pady=(0, 15))
        
        self.st_current_page = tk.StringVar(value="0")
        self.st_total_pages = tk.StringVar(value="0")
        
        progress_info = tk.Frame(prog_frame, bg=self.colors['bg_primary'])
        progress_info.pack(fill='x')
        
        tk.Label(progress_info, text="Pages:", font=('Segoe UI', 9, 'bold')).pack(side='left')
        tk.Label(progress_info, textvariable=self.st_current_page, font=('Segoe UI', 9)).pack(side='left', padx=(5, 0))
        tk.Label(progress_info, text="/", font=('Segoe UI', 9)).pack(side='left', padx=(5, 5))
        tk.Label(progress_info, textvariable=self.st_total_pages, font=('Segoe UI', 9)).pack(side='left')
        
        # Log section
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill='both', expand=True)
        
        # Create scrolled text widget
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.st_log_text = tk.Text(log_frame, 
                                  font=('Courier New', 9),
                                  state='disabled',
                                  yscrollcommand=scrollbar.set,
                                  height=8)
        self.st_log_text.pack(fill='both', expand=True)
        scrollbar.config(command=self.st_log_text.yview)
    
    def browse_st_input_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Input PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.st_input_file_path.set(file_path)
            self.set_default_output_path(file_path, self.st_output_file_path,
                                         self.st_default_output_dir,
                                         "st_courier", "_ST_processed")
    
    def browse_st_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="Save Processed PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.st_output_file_path.set(file_path)
            folder_path = os.path.dirname(file_path)
            if folder_path:
                self.st_default_output_dir.set(folder_path)

    def setup_delhivery_ui(self, parent):
        """Create UI for Delhivery Direct PDF processing"""
        self.delhivery_input_file_path = tk.StringVar()
        self.delhivery_output_file_path = tk.StringVar()
        self.delhivery_current_page = tk.StringVar(value="0")
        self.delhivery_total_pages = tk.StringVar(value="0")

        main_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=15)

        title_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        title_frame.pack(fill='x', pady=(0, 20))

        title_label = tk.Label(title_frame,
                              text="Delhivery Direct Label Processor",
                              font=('Segoe UI', 18, 'bold'),
                              bg=self.colors['bg_primary'],
                              fg=self.colors['text_primary'])
        title_label.pack(anchor='w')

        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="15")
        file_frame.pack(fill='x', pady=(0, 15))

        input_frame = tk.Frame(file_frame)
        input_frame.pack(fill='x', pady=(0, 10))

        tk.Label(input_frame, text="Input PDF:",
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        input_entry_frame = tk.Frame(input_frame)
        input_entry_frame.pack(fill='x', pady=(5, 0))

        self.delhivery_input_entry = ttk.Entry(input_entry_frame,
                                              textvariable=self.delhivery_input_file_path,
                                              font=('Segoe UI', 9),
                                              state='readonly')
        self.delhivery_input_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ttk.Button(input_entry_frame, text="Browse...",
                  command=self.browse_delhivery_input_file).pack(side='right')

        output_frame = tk.Frame(file_frame)
        output_frame.pack(fill='x')

        tk.Label(output_frame, text="Output PDF:",
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        output_entry_frame = tk.Frame(output_frame)
        output_entry_frame.pack(fill='x', pady=(5, 0))

        self.delhivery_output_entry = ttk.Entry(output_entry_frame,
                                               textvariable=self.delhivery_output_file_path,
                                               font=('Segoe UI', 9),
                                               state='readonly')
        self.delhivery_output_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ttk.Button(output_entry_frame, text="Browse...",
                  command=self.browse_delhivery_output_file).pack(side='right')

        default_folder_frame = tk.Frame(file_frame)
        default_folder_frame.pack(fill='x', pady=(10, 0))

        tk.Label(default_folder_frame, text="Default Output Folder:",
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        default_folder_entry_frame = tk.Frame(default_folder_frame)
        default_folder_entry_frame.pack(fill='x', pady=(5, 0))

        self.delhivery_default_output_dir_entry = ttk.Entry(default_folder_entry_frame,
                                                             textvariable=self.delhivery_default_output_dir,
                                                             font=('Segoe UI', 9),
                                                             state='readonly')
        self.delhivery_default_output_dir_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ttk.Button(default_folder_entry_frame, text="Browse Folder",
                  command=lambda: self.browse_default_output_folder(self.delhivery_default_output_dir)).pack(side='right')

        controls_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        controls_frame.pack(fill='x', pady=(0, 15))

        self.delhivery_process_button = ttk.Button(controls_frame, text="Process PDF",
                                                  command=self.process_delhivery_pdf)
        self.delhivery_process_button.pack(side='left', padx=(0, 10))

        self.delhivery_open_pdf_button = ttk.Button(controls_frame, text="Print PDF",
                                                   command=self.open_delhivery_converted_pdf,
                                                   state='disabled')
        self.delhivery_open_pdf_button.pack(side='left', padx=(10, 0))

        prog_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        prog_frame.pack(fill='x', pady=(0, 15))

        progress_info = tk.Frame(prog_frame, bg=self.colors['bg_primary'])
        progress_info.pack(fill='x')

        tk.Label(progress_info, text="Pages:", font=('Segoe UI', 9, 'bold')).pack(side='left')
        tk.Label(progress_info, textvariable=self.delhivery_current_page, font=('Segoe UI', 9)).pack(side='left', padx=(5, 0))
        tk.Label(progress_info, text="/", font=('Segoe UI', 9)).pack(side='left', padx=(5, 5))
        tk.Label(progress_info, textvariable=self.delhivery_total_pages, font=('Segoe UI', 9)).pack(side='left')

        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill='both', expand=True)
        
        # Create scrolled text widget
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.delhivery_log_text = tk.Text(log_frame, 
                                          font=('Courier New', 9),
                                          state='disabled',
                                          yscrollcommand=scrollbar.set,
                                          height=8)
        self.delhivery_log_text.pack(fill='both', expand=True)
        scrollbar.config(command=self.delhivery_log_text.yview)

        # Create default output directory if it doesn't exist
        self.ensure_delhivery_output_dir()

    def browse_delhivery_input_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Delhivery Input PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.delhivery_input_file_path.set(file_path)
            self.set_default_output_path(file_path, self.delhivery_output_file_path,
                                         self.delhivery_default_output_dir,
                                         "delhivery_direct", "_processed")

    def browse_delhivery_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="Save Delhivery Processed PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.delhivery_output_file_path.set(file_path)
            folder_path = os.path.dirname(file_path)
            if folder_path:
                self.delhivery_default_output_dir.set(folder_path)

    def ensure_delhivery_output_dir(self):
        """Ensure the default output directory for Delhivery Direct exists."""
        default_dir = os.path.join(os.path.expanduser("~"), "Documents", "delhivery_direct")
        if not os.path.exists(default_dir):
            try:
                os.makedirs(default_dir)
                print(f"Created default output directory: {default_dir}")
            except Exception as e:
                print(f"Failed to create directory {default_dir}: {e}")

    def get_default_delhivery_output_dir(self):
        """Return and create the Delhivery Direct output folder inside Documents."""
        documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
        output_dir = os.path.join(documents_dir, "delhivery_direct")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def get_default_delhivery_output_path(self, source_path=None):
        """Return a default output path inside the Delhivery Direct Documents folder."""
        output_dir = self.get_default_delhivery_output_dir()
        if source_path:
            base_name = os.path.splitext(os.path.basename(source_path))[0]
        else:
            base_name = "delhivery_direct"
        return os.path.join(output_dir, f"{base_name}_processed.pdf")

    def setup_st_courier_ui(self, parent):
        """Create UI for ST COURIER LABELS with PDF file selection"""
        # Variables for ST tab
        self.st_input_file_path = tk.StringVar()
        self.st_output_file_path = tk.StringVar()
        
        # Main container
        main_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=15)
        
        # Title section
        title_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        title_frame.pack(fill='x', pady=(0, 20))
        
        title_label = tk.Label(title_frame, 
                              text="ST Courier Label Processor",
                              font=('Segoe UI', 18, 'bold'),
                              bg=self.colors['bg_primary'],
                              fg=self.colors['text_primary'])
        title_label.pack(anchor='w')
        
        # File selection section
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="15")
        file_frame.pack(fill='x', pady=(0, 15))
        
        # Input file row
        input_frame = tk.Frame(file_frame)
        input_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(input_frame, text="Input PDF:", 
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        input_entry_frame = tk.Frame(input_frame)
        input_entry_frame.pack(fill='x', pady=(5, 0))
        
        self.st_input_entry = ttk.Entry(input_entry_frame, 
                                       textvariable=self.st_input_file_path,
                                       font=('Segoe UI', 9),
                                       state='readonly')
        self.st_input_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ttk.Button(input_entry_frame, text="Browse...", 
                  command=self.browse_st_input_file).pack(side='right')
        
        # Output file row
        output_frame = tk.Frame(file_frame)
        output_frame.pack(fill='x')
        
        tk.Label(output_frame, text="Output PDF:", 
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        
        output_entry_frame = tk.Frame(output_frame)
        output_entry_frame.pack(fill='x', pady=(5, 0))
        
        self.st_output_entry = ttk.Entry(output_entry_frame, 
                                        textvariable=self.st_output_file_path,
                                        font=('Segoe UI', 9),
                                        state='readonly')
        self.st_output_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        ttk.Button(output_entry_frame, text="Browse...", 
                  command=self.browse_st_output_file).pack(side='right')

        default_folder_frame = tk.Frame(file_frame)
        default_folder_frame.pack(fill='x', pady=(10, 0))

        tk.Label(default_folder_frame, text="Default Output Folder:",
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        default_folder_entry_frame = tk.Frame(default_folder_frame)
        default_folder_entry_frame.pack(fill='x', pady=(5, 0))

        self.st_default_output_dir_entry = ttk.Entry(default_folder_entry_frame,
                                                     textvariable=self.st_default_output_dir,
                                                     font=('Segoe UI', 9),
                                                     state='readonly')
        self.st_default_output_dir_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ttk.Button(default_folder_entry_frame, text="Browse Folder",
                  command=lambda: self.browse_default_output_folder(self.st_default_output_dir)).pack(side='right')
        
        # Control buttons section
        controls_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        controls_frame.pack(fill='x', pady=(0, 15))
        
        self.st_process_button = ttk.Button(controls_frame, text="Process PDF", 
                                           command=self.process_st_pdf)
        self.st_process_button.pack(side='left', padx=(0, 10))
        
        self.st_open_pdf_button = ttk.Button(controls_frame, text="Print PDF", 
                                            command=self.open_st_converted_pdf,
                                            state='disabled')
        self.st_open_pdf_button.pack(side='left', padx=(10, 0))
        
        # Progress section (minimal)
        prog_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        prog_frame.pack(fill='x', pady=(0, 15))
        
        self.st_current_page = tk.StringVar(value="0")
        self.st_total_pages = tk.StringVar(value="0")
        
        progress_info = tk.Frame(prog_frame, bg=self.colors['bg_primary'])
        progress_info.pack(fill='x')
        
        tk.Label(progress_info, text="Pages:", font=('Segoe UI', 9, 'bold')).pack(side='left')
        tk.Label(progress_info, textvariable=self.st_current_page, font=('Segoe UI', 9)).pack(side='left', padx=(5, 0))
        tk.Label(progress_info, text="/", font=('Segoe UI', 9)).pack(side='left', padx=(5, 5))
        tk.Label(progress_info, textvariable=self.st_total_pages, font=('Segoe UI', 9)).pack(side='left')
        
        # Log section
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill='both', expand=True)
        
        # Create scrolled text widget
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.st_log_text = tk.Text(log_frame, 
                                  font=('Courier New', 9),
                                  state='disabled',
                                  yscrollcommand=scrollbar.set,
                                  height=8)
        self.st_log_text.pack(fill='both', expand=True)
        scrollbar.config(command=self.st_log_text.yview)
    
    def browse_st_input_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Input PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.st_input_file_path.set(file_path)
            self.set_default_output_path(file_path, self.st_output_file_path,
                                         self.st_default_output_dir,
                                         "st_courier", "_ST_processed")
    
    def browse_st_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="Save Processed PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.st_output_file_path.set(file_path)
            folder_path = os.path.dirname(file_path)
            if folder_path:
                self.st_default_output_dir.set(folder_path)

    def setup_delhivery_ui(self, parent):
        """Create UI for Delhivery Direct PDF processing"""
        self.delhivery_input_file_path = tk.StringVar()
        self.delhivery_output_file_path = tk.StringVar()
        self.delhivery_current_page = tk.StringVar(value="0")
        self.delhivery_total_pages = tk.StringVar(value="0")

        main_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=15)

        title_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        title_frame.pack(fill='x', pady=(0, 20))

        title_label = tk.Label(title_frame,
                              text="Delhivery Direct Label Processor",
                              font=('Segoe UI', 18, 'bold'),
                              bg=self.colors['bg_primary'],
                              fg=self.colors['text_primary'])
        title_label.pack(anchor='w')

        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="15")
        file_frame.pack(fill='x', pady=(0, 15))

        input_frame = tk.Frame(file_frame)
        input_frame.pack(fill='x', pady=(0, 10))

        tk.Label(input_frame, text="Input PDF:",
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        input_entry_frame = tk.Frame(input_frame)
        input_entry_frame.pack(fill='x', pady=(5, 0))

        self.delhivery_input_entry = ttk.Entry(input_entry_frame,
                                              textvariable=self.delhivery_input_file_path,
                                              font=('Segoe UI', 9),
                                              state='readonly')
        self.delhivery_input_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ttk.Button(input_entry_frame, text="Browse...",
                  command=self.browse_delhivery_input_file).pack(side='right')

        output_frame = tk.Frame(file_frame)
        output_frame.pack(fill='x')

        tk.Label(output_frame, text="Output PDF:",
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        output_entry_frame = tk.Frame(output_frame)
        output_entry_frame.pack(fill='x', pady=(5, 0))

        self.delhivery_output_entry = ttk.Entry(output_entry_frame,
                                               textvariable=self.delhivery_output_file_path,
                                               font=('Segoe UI', 9),
                                               state='readonly')
        self.delhivery_output_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ttk.Button(output_entry_frame, text="Browse...",
                  command=self.browse_delhivery_output_file).pack(side='right')

        default_folder_frame = tk.Frame(file_frame)
        default_folder_frame.pack(fill='x', pady=(10, 0))

        tk.Label(default_folder_frame, text="Default Output Folder:",
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        default_folder_entry_frame = tk.Frame(default_folder_frame)
        default_folder_entry_frame.pack(fill='x', pady=(5, 0))

        self.delhivery_default_output_dir_entry = ttk.Entry(default_folder_entry_frame,
                                                             textvariable=self.delhivery_default_output_dir,
                                                             font=('Segoe UI', 9),
                                                             state='readonly')
        self.delhivery_default_output_dir_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ttk.Button(default_folder_entry_frame, text="Browse Folder",
                  command=lambda: self.browse_default_output_folder(self.delhivery_default_output_dir)).pack(side='right')

        controls_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        controls_frame.pack(fill='x', pady=(0, 15))

        self.delhivery_process_button = ttk.Button(controls_frame, text="Process PDF",
                                                  command=self.process_delhivery_pdf)
        self.delhivery_process_button.pack(side='left', padx=(0, 10))

        self.delhivery_open_pdf_button = ttk.Button(controls_frame, text="Print PDF",
                                                   command=self.open_delhivery_converted_pdf,
                                                   state='disabled')
        self.delhivery_open_pdf_button.pack(side='left', padx=(10, 0))

        prog_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        prog_frame.pack(fill='x', pady=(0, 15))

        progress_info = tk.Frame(prog_frame, bg=self.colors['bg_primary'])
        progress_info.pack(fill='x')

        tk.Label(progress_info, text="Pages:", font=('Segoe UI', 9, 'bold')).pack(side='left')
        tk.Label(progress_info, textvariable=self.delhivery_current_page, font=('Segoe UI', 9)).pack(side='left', padx=(5, 0))
        tk.Label(progress_info, text="/", font=('Segoe UI', 9)).pack(side='left', padx=(5, 5))
        tk.Label(progress_info, textvariable=self.delhivery_total_pages, font=('Segoe UI', 9)).pack(side='left')

        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.pack(fill='both', expand=True)
        
        # Create scrolled text widget
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.delhivery_log_text = tk.Text(log_frame, 
                                          font=('Courier New', 9),
                                          state='disabled',
                                          yscrollcommand=scrollbar.set,
                                          height=8)
        self.delhivery_log_text.pack(fill='both', expand=True)
        scrollbar.config(command=self.delhivery_log_text.yview)

        # Create default output directory if it doesn't exist
        self.ensure_delhivery_output_dir()

    def browse_delhivery_input_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Delhivery Input PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.delhivery_input_file_path.set(file_path)
            self.set_default_output_path(file_path, self.delhivery_output_file_path,
                                         self.delhivery_default_output_dir,
                                         "delhivery_direct", "_processed")

    def browse_delhivery_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="Save Delhivery Processed PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.delhivery_output_file_path.set(file_path)
            folder_path = os.path.dirname(file_path)
            if folder_path:
                self.delhivery_default_output_dir.set(folder_path)

    def ensure_delhivery_output_dir(self):
        """Ensure the default output directory for Delhivery Direct exists."""
        default_dir = os.path.join(os.path.expanduser("~"), "Documents", "delhivery_direct")
        if not os.path.exists(default_dir):
            try:
                os.makedirs(default_dir)
                print(f"Created default output directory: {default_dir}")
            except Exception as e:
                print(f"Failed to create directory {default_dir}: {e}")

    def get_default_delhivery_output_dir(self):
        """Return and create the Delhivery Direct output folder inside Documents."""
        documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
        output_dir = os.path.join(documents_dir, "delhivery_direct")
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def get_default_delhivery_output_path(self, source_path=None):
        """Return a default output path inside the Delhivery Direct Documents folder."""
        output_dir = self.get_default_delhivery_output_dir()
        if source_path:
            base_name = os.path.splitext(os.path.basename(source_path))[0]
        else:
            base_name = "delhivery_direct"
        return os.path.join(output_dir, f"{base_name}_processed.pdf")

    def process_st_pdf(self):
        if not self.st_input_file_path.get():
            messagebox.showerror("Error", "Please select an input PDF file.")
            return
        
        if not self.st_output_file_path.get():
            messagebox.showerror("Error", "Please select an output PDF file.")
            return
        
        self.st_log_text.config(state='normal')
        self.st_log_text.delete('1.0', 'end')
        self.st_log_text.config(state='disabled')
        
        self.st_process_button.config(state="disabled", text="Processing...")
        self.st_open_pdf_button.config(state="disabled")
        
        thread = threading.Thread(target=self._process_st_pdf_thread, 
                                args=(self.st_input_file_path.get(), self.st_output_file_path.get()))
        thread.daemon = True
        thread.start()

    def process_delhivery_pdf(self):
        if not self.delhivery_input_file_path.get():
            messagebox.showerror("Error", "Please select an input PDF file.")
            return

        if not self.delhivery_output_file_path.get():
            messagebox.showerror("Error", "Please select an output PDF file.")
            return

        self.delhivery_log_text.config(state='normal')
        self.delhivery_log_text.delete('1.0', 'end')
        self.delhivery_log_text.config(state='disabled')

        self.delhivery_process_button.config(state="disabled", text="Processing...")
        self.delhivery_open_pdf_button.config(state="disabled")

        thread = threading.Thread(target=self._process_delhivery_pdf_thread,
                                  args=(self.delhivery_input_file_path.get(), self.delhivery_output_file_path.get()))
        thread.daemon = True
        thread.start()

    def _process_delhivery_pdf_thread(self, input_path, output_path):
        try:
            self.delhivery_log_message("Starting Delhivery Direct PDF processing...")

            doc = fitz.open(input_path)
            total_pages = len(doc)
            self.delhivery_total_pages.set(str(total_pages))
            self.delhivery_log_message(f"Opened PDF with {total_pages} pages")

            marked_pages = []
            self.delhivery_log_message("Processing pages...")

            for i, page in enumerate(doc):
                self.delhivery_current_page.set(str(i + 1))
                if i % 25 == 0 or i == total_pages - 1:
                    self.delhivery_log_message(f"Processing page {i+1}/{total_pages}")

                text = page.get_text()
                products = self.extract_delhivery_products(text)
                if products:
                    marked_pages.append((i, products))

            self.delhivery_log_message(f"Found {len(marked_pages)} pages with recognized products")
            self.delhivery_log_message("Sorting pages by product and quantity...")

            final_page_order = self.sort_delhivery_marked_pages(marked_pages)
            self.delhivery_log_message("Creating new PDF with reordered pages...")

            new_doc = fitz.open()
            for page_num, products in final_page_order:
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                new_page = new_doc[-1]

                if products:
                    label_parts = []
                    for family_code, qty, _ in products:
                        family_name = {0: 'OIL', 1: 'POTLI', 2: 'VARICO'}.get(family_code, 'OTHER')
                        label_parts.append(self.format_product_label(family_name, qty))
                    label_text = ' | '.join(label_parts)
                    marker_x = 20
                    marker_y = new_page.rect.y1 - 72
                    new_page.insert_text(
                        fitz.Point(marker_x, marker_y),
                        label_text,
                        fontname="Courier-Bold",
                        fontsize=12,
                        color=(1, 0, 0)
                    )

                text = new_page.get_text()
                for line in text.splitlines():
                    line_str = line.strip()
                    line_upper = line_str.upper()
                    if re.match(r'^(PH|PHONE|MOBILE)\s*[:\-]?\s*\+?\d', line_upper):
                        rects = new_page.search_for(line_str)
                        for rect in rects:
                            p1 = fitz.Point(rect.x0, rect.y1 + 1)
                            p2 = fitz.Point(rect.x1, rect.y1 + 1)
                            new_page.draw_line(p1, p2, color=(0, 0, 0), width=2)
                            p3 = fitz.Point(rect.x0, rect.y0 - 1)
                            p4 = fitz.Point(rect.x1, rect.y0 - 1)
                            new_page.draw_line(p3, p4, color=(0, 0, 0), width=2)
                            new_page.insert_text(
                                (rect.x1 + 10, rect.y1 - 2),
                                "<-- CALL THIS NUMBER",
                                fontname="hebo",
                                fontsize=12,
                                color=(0, 0, 0)
                            )

            new_doc.save(output_path)
            new_doc.close()
            doc.close()

            self.delhivery_log_message("PDF processing completed successfully!")
            self.root.after(0, self.delhivery_processing_complete, output_path)

        except Exception as e:
            self.delhivery_log_message(f"ERROR: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to process PDF: {e}"))
            self.delhivery_process_button.config(state="normal", text="Process PDF")
            self.delhivery_open_pdf_button.config(state="disabled")

    def delhivery_processing_complete(self, output_path):
        self.delhivery_process_button.config(state="normal", text="Process PDF")
        if os.path.exists(output_path):
            self.delhivery_open_pdf_button.config(state="normal")
            messagebox.showinfo("Success", f"PDF processed successfully!\n\nOutput saved to:\n{output_path}")
        else:
            self.delhivery_open_pdf_button.config(state="disabled")

    def open_delhivery_converted_pdf(self):
        output_path = self.delhivery_output_file_path.get()
        if output_path and os.path.exists(output_path):
            try:
                self.delhivery_log_message("Opening converted PDF...")
                os.startfile(output_path)
            except Exception as e:
                error_msg = f"Could not open PDF: {e}"
                self.delhivery_log_message(error_msg)
                messagebox.showerror("Error", error_msg)
        else:
            messagebox.showerror("Error", "Converted PDF not found.")

    def delhivery_log_message(self, message):
        self.root.after(0, lambda: self._append_delhivery_log(message))

    def _append_delhivery_log(self, message):
        self.delhivery_log_text.config(state='normal')
        self.delhivery_log_text.insert('end', message + '\n')
        self.delhivery_log_text.see('end')
        self.delhivery_log_text.config(state='disabled')

    def extract_delhivery_products(self, text):
        """Extract product families and quantities from Delhivery Direct label text."""
        seen = set()
        products = []
        lines = text.splitlines()

        def assign_family(product_label):
            normalized = product_label.lower()
            if 'potli' in normalized:
                return 'Potli', 'Tulir Naturals - Massager Potli'
            if 'varico' in normalized:
                return 'Varico', 'Tulir Naturals - Varico Oil'
            if 'oil' in normalized or '100ml' in normalized:
                return 'Oil', 'Tulir Naturals Oil 100ml'
            return 'Unknown', product_label.strip()

        def extract_qty(index):
            qty = 1
            qty_patterns = [
                r'qty\s*[:\-]?\s*(\d+)',
                r'x\s*(\d+)',
                r'(\d+)\s*pcs?',
                r'^(\d+)$'
            ]

            for offset in range(0, 5):
                scan_index = index + offset
                if scan_index >= len(lines):
                    break
                candidate = lines[scan_index].strip()
                if not candidate:
                    continue
                for pattern in qty_patterns:
                    match = re.search(pattern, candidate, re.IGNORECASE)
                    if match:
                        return int(match.group(1))
            return qty

        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            normalized_line = re.sub(r'\s+', ' ', line_stripped).lower()
            if 'product name' in normalized_line or 'qty' in normalized_line:
                continue
            if normalized_line.startswith('seller:'):
                continue
            if not normalized_line.startswith('tulir naturals'):
                continue

            family, product_name = assign_family(line_stripped)
            qty = extract_qty(i)
            family_code = 0 if family == 'Oil' else 1 if family == 'Potli' else 2 if family == 'Varico' else 3
            product_key = (family_code, qty, product_name)
            if product_key not in seen:
                seen.add(product_key)
                products.append(product_key)

        if not products:
            sku_labels = self.extract_skus_from_page(lines)
            for sku, label_text in sku_labels:
                qty = 1
                if 'x' in label_text:
                    try:
                        qty = int(label_text.split('x')[1])
                    except Exception:
                        qty = 1

                product_name = label_text.replace('→', '').strip()
                family, product_name = assign_family(product_name)
                family_code = 0 if family == 'Oil' else 1 if family == 'Potli' else 2 if family == 'Varico' else 3
                product_key = (family_code, qty, product_name)
                if product_key not in seen:
                    seen.add(product_key)
                    products.append(product_key)

        return products

    def sort_delhivery_marked_pages(self, marked_pages):
        """Sort Delhivery pages by product family and quantity, grouping identical product+qty together."""
        def get_sort_key(products_list):
            if not products_list:
                return (2, tuple(), "")

            is_multi = 1 if len(products_list) > 1 else 0
            sorted_products = sorted(products_list, key=lambda x: (x[0], x[1]))
            product_qty_pairs = tuple((p[0], p[1]) for p in sorted_products)
            primary_name = sorted_products[0][2] if sorted_products else ""
            return (is_multi, product_qty_pairs, primary_name)

        sorted_pages = sorted(marked_pages, key=lambda x: get_sort_key(x[1]))

        self.delhivery_log_message(f"\nSorted order for {len(sorted_pages)} pages:")
        for idx, (page_num, products) in enumerate(sorted_pages, 1):
            product_details = []
            for p in products:
                family_name = {0: 'Oil', 1: 'Potli', 2: 'Varico'}.get(p[0], 'Other')
                product_details.append(f"{family_name} qty {p[1]}")
            details_str = ' | '.join(product_details)
            self.delhivery_log_message(f"  {idx}. Page {page_num + 1}: {details_str}")

        return sorted_pages

    def _process_st_pdf_thread(self, input_path, output_path):
        try:
            self.st_log_message("Starting ST PDF processing...")
            
            doc = fitz.open(input_path)
            total_pages = len(doc)
            self.st_total_pages.set(str(total_pages))
            self.st_log_message(f"Opened PDF with {total_pages} pages")
            
            marked_pages = []
            
            self.st_log_message("Processing pages...")
            
            for i, page in enumerate(doc):
                self.st_current_page.set(str(i + 1))
                if i % 25 == 0 or i == total_pages - 1:
                    self.st_log_message(f"Processing page {i+1}/{total_pages}")
                
                text = page.get_text()
                
                # Extract products from this page using ST product names
                products = self.extract_st_products(text)
                
                if products:
                    marked_pages.append((i, products))
            
            self.st_log_message(f"Found {len(marked_pages)} pages with products")
            
            self.st_log_message("Sorting pages by product and quantity...")
            final_page_order = self.sort_st_marked_pages(marked_pages)
            
            self.st_log_message("Creating new PDF with reordered pages...")
            new_doc = fitz.open()
            
            ordered_pages = [i for i, _ in final_page_order]
            
            for page_num in ordered_pages:
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                # Highlight the Deliver To phone number to ensure couriers use it
                new_page = new_doc[-1]
                text = new_page.get_text()
                for line in text.splitlines():
                    line_str = line.strip()
                    line_upper = line_str.upper()
                    if re.match(r'^PH(?:ONE)?\s*:\s*\+?\d', line_upper):
                        rects = new_page.search_for(line_str)
                        for rect in rects:
                            # Instead of a border or box, let's draw an underline, 
                            # an overline, and increase visibility by stamping a 
                            # prominent "CALL THIS -->" text right next to it.
                            
                            # Thicker underline
                            p1 = fitz.Point(rect.x0, rect.y1 + 1)
                            p2 = fitz.Point(rect.x1, rect.y1 + 1)
                            new_page.draw_line(p1, p2, color=(0, 0, 0), width=2)
                            
                            # Thicker overline
                            p3 = fitz.Point(rect.x0, rect.y0 - 1)
                            p4 = fitz.Point(rect.x1, rect.y0 - 1)
                            new_page.draw_line(p3, p4, color=(0, 0, 0), width=2)
                            
                            # Add a guiding pointer text to the right 
                            # Adjust X coordinate depending on page width, 
                            # but usually ST labels have some whitespace right of the phone
                            new_page.insert_text(
                                (rect.x1 + 10, rect.y1 - 2),
                                "<-- CALL THIS NUMBER",
                                fontname="hebo",
                                fontsize=12,
                                color=(0, 0, 0)
                            )
            
            new_doc.save(output_path)
            new_doc.close()
            doc.close()
            
            self.st_log_message("PDF processing completed successfully!")
            self.root.after(0, self.st_processing_complete, output_path)
        
        except Exception as e:
            self.st_log_message(f"ERROR: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to process PDF: {e}"))
            self.st_process_button.config(state="normal", text="Process PDF")
            self.st_open_pdf_button.config(state="disabled")
    
    def st_processing_complete(self, output_path):
        self.st_process_button.config(state="normal", text="Process PDF")
        if os.path.exists(output_path):
            self.st_open_pdf_button.config(state="normal")
            messagebox.showinfo("Success", f"PDF processed successfully!\n\nOutput saved to:\n{output_path}")
        else:
            self.st_open_pdf_button.config(state="disabled")
    
    def open_st_converted_pdf(self):
        output_path = self.st_output_file_path.get()
        if output_path and os.path.exists(output_path):
            try:
                self.st_log_message("Opening converted PDF...")
                os.startfile(output_path)
            except Exception as e:
                error_msg = f"Could not open PDF: {e}"
                self.st_log_message(error_msg)
                messagebox.showerror("Error", error_msg)
        else:
            messagebox.showerror("Error", "Converted PDF not found.")
    
    def st_log_message(self, message):
        """Append message to ST log"""
        self.root.after(0, lambda: self._append_st_log(message))
    
    def _append_st_log(self, message):
        self.st_log_text.config(state='normal')
        self.st_log_text.insert('end', message + '\n')
        self.st_log_text.see('end')
        self.st_log_text.config(state='disabled')
    
    def extract_st_products(self, text):
        """
        Extract unique product names and quantities from ST label text in table format.
        Looks for "Product Name" and "Qty" columns in the table.
        Returns: list of (product_family, qty, product_name) tuples, deduplicated
        """
        seen = set()
        products = []
        
        # Define ST product patterns - these are the actual product names
        st_products = {
            r'(?i)tulir\s+naturals\s+oil\s+100ml': ('Oil', 'Tulir Naturals Oil 100ml'),
            r'(?i)tulir\s+naturals\s*-?\s*massager\s+potli': ('Potli', 'Tulir Naturals - Massager Potli'),
            r'(?i)tulir\s+naturals\s*-?\s*varico\s+oil': ('Varico', 'Tulir Naturals - Varico Oil'),
        }
        
        lines = text.splitlines()
        
        # Find lines with product names
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            if not line_stripped:
                continue
            
            # Check each product pattern
            for pattern, (family, product_name) in st_products.items():
                if re.search(pattern, line):
                    qty = 1
                    
                    # Strategy 1: Look for pipe-separated value (table format with |)
                    if '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 2:
                            qty_part = parts[-1].strip()
                            qty_match = re.search(r'(\d+)', qty_part)
                            if qty_match:
                                qty = int(qty_match.group(1))
                    
                    # Strategy 2: Look for quantity on next line (below product name in table)
                    elif i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        qty_match = re.search(r'^\d+$', next_line)  # Just a number
                        if qty_match:
                            qty = int(next_line)
                    
                    # Strategy 3: Look for digit at end of current line
                    if qty == 1:
                        qty_match = re.search(r'(\d+)\s*$', line)
                        if qty_match:
                            qty_str = qty_match.group(1)
                            # Make sure it's not part of the product name (like "100ml")
                            if qty_str not in line_stripped.split()[-1] or '100' not in line_stripped:
                                qty = int(qty_str)
                    
                    # Family mapping
                    if family == 'Oil':
                        family_code = 0
                    elif family == 'Potli':
                        family_code = 1
                    elif family == 'Varico':
                        family_code = 2
                    else:
                        family_code = 3
                    
                    # Deduplicate
                    product_key = (family_code, qty, product_name)
                    if product_key not in seen:
                        seen.add(product_key)
                        products.append(product_key)
                    
                    break
        
        return products
    
    def sort_st_marked_pages(self, marked_pages):
        """
        Sort pages by product family and quantity, grouping identical product+qty together.
        Format: (page_index, [(family_code, qty, product_name), ...])
        Returns: list of (page_index, products) sorted correctly
        """
        def get_sort_key(products_list):
            """
            Create sort key that groups pages by product+quantity combination.
            Sorting priority:
            1. Single product pages before multi-product pages
            2. For each product in order: (family, qty)
            3. Product name as final tiebreaker
            """
            if not products_list:
                return (2, tuple(), "")
            
            # Check if single or multi product
            is_multi = 1 if len(products_list) > 1 else 0
            
            # Sort products within page by family, then quantity
            sorted_products = sorted(products_list, key=lambda x: (x[0], x[1]))
            
            # Create a tuple of (family, qty) pairs for each product - this is the main grouping key
            product_qty_pairs = tuple((p[0], p[1]) for p in sorted_products)
            
            # Get primary product name for tiebreaker
            primary_name = sorted_products[0][2] if sorted_products else ""
            
            return (is_multi, product_qty_pairs, primary_name)
        
        # Sort all pages
        sorted_pages = sorted(marked_pages, key=lambda x: get_sort_key(x[1]))
        
        # Log the result with detailed info
        self.st_log_message(f"\nSorted order for {len(sorted_pages)} pages:")
        for idx, (page_num, products) in enumerate(sorted_pages, 1):
            # Show each product with family and qty
            product_details = []
            for p in products:
                family_name = {0: "Oil", 1: "Potli", 2: "Varico"}.get(p[0], "Other")
                product_details.append(f"{family_name} qty {p[1]}")
            details_str = " | ".join(product_details)
            self.st_log_message(f"  {idx}. Page {page_num + 1}: {details_str}")
        
        return sorted_pages



    def _process_shopify_updates(self, base_url, token):
        headers = {
            "X-Shopify-Access-Token": token,
            "Content-Type": "application/json"
        }
        
        updated_ids = []
        failed_ids = []
        
        total = len(self.courier_orders)
        
        for index, item in enumerate(self.courier_orders):
            order_id = str(item.get('order_id', '')).strip()
            
            # Skip if no order ID (explicit user request: "updates should only happen for orders with order id")
            if not order_id:
                continue
                
            try:
                # 1. Search for the order ID
                # We assume the user inputs the "Order Name" (e.g. 1001) which matches 'name' or 'order_number' in Shopify
                # The API allows searching by name.
                search_url = f"{base_url}/admin/api/2023-10/orders.json?name={order_id}&status=any"
                resp = requests.get(search_url, headers=headers)
                
                if resp.status_code == 200:
                    orders = resp.json().get("orders", [])
                    target_order = None
                    
                    # Exact Match Check
                    for o in orders:
                        # Match name (e.g. "#1001" or "1001")
                        if str(o.get('order_number')) == order_id or str(o.get('name')) == order_id or str(o.get('name')) == f"#{order_id}":
                            target_order = o
                            break
                    
                    if target_order:
                        shopify_id = target_order.get('id')
                        current_note = target_order.get('note') or ""
                        
                        today_str = datetime.date.today().strftime("%d-%m-%Y")
                        comment = f"Shipped Via ST courier {today_str}"
                        
                        # Avoid duplicate comments (Check for base message to prevent multi-date duplication if processed twice)
                        if "Shipped Via ST courier" in current_note:
                            updated_ids.append(order_id) # Already done
                            continue
                            
                        new_note = f"{current_note}\n{comment}".strip()
                        
                        # 2. Update the order
                        update_url = f"{base_url}/admin/api/2023-10/orders/{shopify_id}.json"
                        payload = {
                            "order": {
                                "id": shopify_id,
                                "note": new_note
                            }
                        }
                        
                        upd_resp = requests.put(update_url, json=payload, headers=headers)
                        if upd_resp.status_code == 200:
                            updated_ids.append(order_id)
                        else:
                            print(f"Failed to update {order_id}: {upd_resp.text}")
                            failed_ids.append(order_id)
                    else:
                        print(f"Order {order_id} not found in Shopify")
                        failed_ids.append(order_id)
                else:
                    print(f"Search failed for {order_id}: {resp.status_code}")
                    failed_ids.append(order_id)
                    
            except Exception as e:
                print(f"Error processing {order_id}: {e}")
                failed_ids.append(order_id)
                
        # Report results
        msg = f"Processed {total} orders.\nSuccess: {len(updated_ids)}\nFailed: {len(failed_ids)}"
        if failed_ids:
            msg += f"\nFailed IDs: {', '.join(failed_ids)}"
            
        self.root.after(0, lambda: messagebox.showinfo("Shopify Update Report", msg))

    def open_settings(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Settings")
        settings_win.geometry("500x350")
        
        tk.Label(settings_win, text="Email:").pack(anchor='w', padx=10, pady=(10, 0))
        email_var = tk.StringVar(value=self.shiprocket_config.get("email", ""))
        ttk.Entry(settings_win, textvariable=email_var, width=50).pack(padx=10, pady=5)
        
        tk.Label(settings_win, text="Password:").pack(anchor='w', padx=10, pady=(10, 0))
        pwd_var = tk.StringVar(value=self.shiprocket_config.get("password", ""))
        ttk.Entry(settings_win, textvariable=pwd_var, width=50, show="*").pack(padx=10, pady=5)
        
        # Shopify Settings
        ttk.Separator(settings_win, orient='horizontal').pack(fill='x', pady=15)
        
        tk.Label(settings_win, text="Shopify Store URL (e.g. my-store.myshopify.com):").pack(anchor='w', padx=10, pady=(0, 0))
        shop_url_var = tk.StringVar(value=self.shiprocket_config.get("shopify_url", ""))
        ttk.Entry(settings_win, textvariable=shop_url_var, width=50).pack(padx=10, pady=5)

        tk.Label(settings_win, text="Shopify Access Token:").pack(anchor='w', padx=10, pady=(10, 0))
        shop_token_var = tk.StringVar(value=self.shiprocket_config.get("shopify_token", ""))
        ttk.Entry(settings_win, textvariable=shop_token_var, width=50, show="*").pack(padx=10, pady=5)
        
        def save():
            self.shiprocket_config["email"] = email_var.get().strip()
            self.shiprocket_config["password"] = pwd_var.get().strip()
            self.shiprocket_config["shopify_url"] = shop_url_var.get().strip()
            self.shiprocket_config["shopify_token"] = shop_token_var.get().strip()
            self.save_config()
            settings_win.destroy()
            messagebox.showinfo("Saved", "Settings saved successfully.")
            
        ttk.Button(settings_win, text="Save", command=save).pack(pady=20)

    def fetch_shiprocket_details(self):
        order_key = self.c_order_id.get().strip()
        if not order_key:
            messagebox.showwarning("Required", "Please enter an Order ID")
            return
            
        self._trigger_fetch(order_key, search_type="order_id")

    def fetch_shiprocket_by_phone(self):
        phone_key = self.c_phone.get().strip()
        if not phone_key:
            messagebox.showwarning("Required", "Please enter a Phone Number")
            return
            
        self._trigger_fetch(phone_key, search_type="phone")

    def _trigger_fetch(self, search_key, search_type):
        email = self.shiprocket_config.get("email")
        password = self.shiprocket_config.get("password")
        
        if not email or not password:
            messagebox.showerror("Configuration Error", "Please configure Shiprocket settings first.")
            self.open_settings()
            return
            
        threading.Thread(target=self._fetch_sr_thread, args=(email, password, search_key, search_type)).start()

    def _auth_shiprocket(self, email, password):
        url = "https://apiv2.shiprocket.in/v1/external/auth/login"
        payload = {"email": email, "password": password}
        try:
            resp = requests.post(url, json=payload)
            if resp.status_code == 200:
                token = resp.json().get("token")
                self.shiprocket_config["token"] = token
                self.save_config()
                return token
        except Exception as e:
            print(f"Auth failed: {e}")
        return None

    def _fetch_sr_thread(self, email, password, search_key, search_type="order_id"):
        try:
            token = self.shiprocket_config.get("token")
            # If no token, or if previous request fails (assumed expired), try to login
            if not token:
                token = self._auth_shiprocket(email, password)
                if not token:
                    self.root.after(0, lambda: messagebox.showerror("Auth Error", "Failed to login to Shiprocket."))
                    return

            # Search Order
            headers = {"Authorization": f"Bearer {token}"}
            url = f"https://apiv2.shiprocket.in/v1/external/orders?search={search_key}"
            
            response = requests.get(url, headers=headers)
            # print(response.text) # Debug

            # If 401 Unauthorized, token expired. Retry once.
            if response.status_code == 401:
                token = self._auth_shiprocket(email, password)
                if token:
                    headers = {"Authorization": f"Bearer {token}"}
                    response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                data_list = data.get("data", [])
                
                target_order = None
                
                if search_type == "order_id":
                    # Find exact match
                    for order in data_list:
                        if (str(order.get("channel_order_id")) == search_key or 
                            str(order.get("id")) == search_key):
                            target_order = order
                            break
                    # Fuzzy fallback
                    if not target_order and data_list:
                        for order in data_list:
                             if search_key in str(order.get("channel_order_id", "")):
                                 target_order = order
                                 break
                                 
                elif search_type == "phone":
                    # Filter for phone match if needed? Or just take the latest from the search results
                    # The search endpoint is generic. It usually returns orders matching the term.
                    # We want the LATEST one. 
                    # Usually `data_list` is paginated. We assume [0] is latest or we sort.
                    if data_list:
                        # Sort by ID descending (assuming higher ID = newer) or created_at
                        # Let's try to sort by 'id' desc
                        data_list.sort(key=lambda x: x.get('id', 0), reverse=True)
                        target_order = data_list[0]

                if target_order:
                    self.root.after(0, self._populate_sr_data, target_order)
                else:
                    self.root.after(0, lambda: messagebox.showinfo("Not Found", f"No order found for {search_key}"))
            else:
                self.root.after(0, lambda: messagebox.showerror("API Error", f"Failed to fetch: {response.status_code}"))
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Connection failed: {str(e)}"))

    def _populate_sr_data(self, order):
        # Debug: Print full order data
        print("Shiprocket Order Data:", json.dumps(order, indent=2))

        # Extract Address
        fname = order.get("customer_name", "")
        addr1 = order.get("customer_address", "")
        addr2 = order.get("customer_address_2", "")
        city = order.get("customer_city", "")
        state = order.get("customer_state", "")
        pincode = order.get("customer_pincode", "")
        country = order.get("customer_country", "")
        
        lines = [fname]
        if addr1: lines.append(addr1)
        if addr2: lines.append(addr2)
        
        loc_parts = []
        if city: loc_parts.append(city)
        if state: loc_parts.append(state)
        if pincode: loc_parts.append(pincode)
        
        if loc_parts: lines.append(", ".join(loc_parts))
        if country: lines.append(country)
        
        full_address = "\n".join(lines)
        
        # Phone
        phone = order.get("customer_phone", "")
        
        # Phone Alternates
        if not phone or "xxxx" in str(phone).lower():
            alternates = [
                order.get("billing_phone"),
                order.get("shipping_phone"),
                order.get("pickup_phone"),
                order.get("phone")
            ]
            for p in alternates:
                if p and "xxxx" not in str(p).lower():
                    phone = p
                    break
        
        # Items
        items = []
        for product in order.get("products", []):
            name = product.get("name")
            qty = product.get("quantity")
            items.append(f"{name} x{qty}")
            
        items_str = ", ".join(items)
        
        # Update UI - ensure to set Order ID if fetched by phone
        self.c_order_id.delete(0, tk.END)
        self.c_order_id.insert(0, str(order.get("channel_order_id") or order.get("id")))
        
        self.c_phone.delete(0, tk.END)
        self.c_phone.insert(0, str(phone))
        
        self.c_items.delete(0, tk.END)
        self.c_items.insert(0, items_str)
        
        self.c_address.delete("1.0", tk.END)
        self.c_address.insert("1.0", full_address)
        
        # messagebox.showinfo("Success", "Order details fetched from Shiprocket!")

    def add_courier_order(self):
        order_id = self.c_order_id.get().strip()
        phone = self.c_phone.get().strip()
        items = self.c_items.get().strip()
        address = self.c_address.get("1.0", tk.END).strip()
        
        if not order_id or not address:
            messagebox.showwarning("Missing Info", "Order ID and Address are required.")
            return

        self.courier_orders.append({
            'order_id': order_id,
            'phone': phone,
            'items': items,
            'address': address
        })
        
        self.tree.insert('', tk.END, values=(order_id, phone, items, address.replace('\n', ', ')))
        
        # Clear inputs
        self.c_order_id.delete(0, tk.END)
        self.c_phone.delete(0, tk.END)
        self.c_items.delete(0, tk.END)
        self.c_address.delete("1.0", tk.END)
        self.c_order_id.focus()

    def delete_courier_order(self):
        selected = self.tree.selection()
        if not selected:
            return
            
        for item in selected:
            values = self.tree.item(item)['values']
            # Remove from internal list (simplistic match)
            self.courier_orders = [o for o in self.courier_orders if str(o['order_id']) != str(values[0])]
            self.tree.delete(item)

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIxxxxxx
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
            
        return os.path.join(base_path, relative_path)

    def generate_courier_labels(self):
        if not self.courier_orders:
            messagebox.showinfo("Empty Queue", "No orders to process.")
            return
            
        # Generate filename: ManualLabel-Today'sDate-Unique5Digit.pdf
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        unique_id = random.randint(10000, 99999)
        filename = f"ManualLabel-{today_str}-{unique_id}.pdf"
        
        # Ensure it saves in current directory or documents? User said "create the label", implying current dir is fine.
        filename = os.path.abspath(filename)
            
        # Load logo data once for optimization
        logo_data = None
        # Use resource_path to find the bundled logo
        logo_path = self.resource_path("Logo.png")
        if os.path.exists(logo_path):
            try:
                with open(logo_path, "rb") as f:
                    logo_data = f.read()
            except Exception as e:
                print(f"Failed to load logo: {e}")
        else:
             print(f"Logo not found at {logo_path}")

        try:
            doc = fitz.open()
            from_address = "From:\nTulir Naturals\nEdaikazhinadu, kadapakkam\ncheyyur Taluk, Chengalpat district\n603304\nPh: 8778469045"
            
            for order in self.courier_orders:
                is_4x4 = self.courier_4x4_var.get()
                
                # Dimensions
                # 4x6: 288 x 432
                # 4x4: 288 x 288
                page_height = 288 if is_4x4 else 432
                
                page = doc.new_page(width=288, height=page_height)
                
                # Draw Box
                rect = fitz.Rect(10, 10, 278, page_height - 10)
                page.draw_rect(rect)
                
                y = 15
                if logo_data:
                    # Centered Logo
                    # Dynamic sizing based on format - Reduced sizes as per request
                    logo_h = 35 if is_4x4 else 50
                    # x starts at (288-100)/2 = 94. Ends at 194.
                    
                    logo_rect = fitz.Rect(94, 10, 194, 10 + logo_h)
                    page.insert_image(logo_rect, stream=logo_data, keep_proportion=True)
                    
                    y = 10 + logo_h + 2 if is_4x4 else 10 + logo_h + 5
                    
                    # Centered Bold Text
                    text_h = 25 if is_4x4 else 30
                    text_size = 14 if is_4x4 else 18
                    
                    text_rect = fitz.Rect(0, y, 288, y + text_h)
                    page.insert_textbox(text_rect, "Tulir Naturals", 
                                      fontname="hebo", fontsize=text_size,
                                      color=(0.1, 0.35, 0.1),
                                      align=1) # 1 = Center
                    y += text_h - 5 # Tighter spacing after title 
                else:
                    # Fallback text only
                    y = 30
                    page.insert_text((20, y), "TULIR NATURALS", fontname="helv", fontsize=14)
                    y += 25
                
                # Divider Line
                page.draw_line((10, y), (278, y))
                y += 10 if is_4x4 else 20
                
                # Order Details
                page.insert_text((20, y), f"Order ID: {order['order_id']}", fontname="helv", fontsize=10)
                y += 12 if is_4x4 else 15
                
                if order['items']:
                    # Simple wrap for items if needed, or just cut off
                    # For 4x4 we might need smaller font for long items
                    item_font_size = 8 if is_4x4 else 10
                    page.insert_text((20, y), f"Items: {order['items']}", fontname="helv", fontsize=item_font_size)
                    y += 15 if is_4x4 else 20
                
                page.draw_line((10, y), (278, y))
                y += 10 if is_4x4 else 20
                
                # To Address
                # 'hebo' is the PyMuPDF code for Helvetica-Bold
                page.insert_text((20, y), "To:", fontname="hebo", fontsize=11)
                y += 12 if is_4x4 else 15
                
                # Split address into lines
                addr_lines = order['address'].split('\n')
                for line in addr_lines:
                    page.insert_text((25, y), line, fontname="helv", fontsize=10)
                    y += 10 if is_4x4 else 12
                
                # Phone
                phone_val = str(order['phone'])
                if phone_val and "xxxx" not in phone_val.lower():
                    y += 5
                    page.insert_text((25, y), f"Ph: {phone_val}", fontname="hebo", fontsize=10)
                    y += 15 if is_4x4 else 20
                
                # Spacer and From Address
                # For 4x4, we need to be careful not to overflow
                # We enforce a bottom area for From Address
                
                # Compact From Address for 4x4
                final_from_address = from_address
                if is_4x4:
                    # Compact to fewer lines
                    # From: Tulir Naturals
                    # Address lines combined
                    final_from_address = "From: Tulir Naturals\nEdaikazhinadu, kadapakkam\ncheyyur Taluk, Chengalpat district - 603304\nPh: 8778469045"
                
                # Calculate required height approx: 4 lines * 9pts = 36pts
                # Start higher up
                from_area_height = 55 if is_4x4 else 70
                from_y_start = page_height - from_area_height if is_4x4 else max(y, 250)
                
                line_y = from_y_start
                 
                page.draw_line((10, line_y), (278, line_y))
                
                from_text_y = line_y + 10 if is_4x4 else line_y + 15
                from_font_size = 8 if is_4x4 else 9
                
                for line in final_from_address.split('\n'):
                    page.insert_text((20, from_text_y), line, fontname="helv", fontsize=from_font_size)
                    from_text_y += 10 if is_4x4 else 12
                
            # Save compressed
            # Save to Downloads folder
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            # filename is already generated above
            full_path = os.path.join(downloads_path, filename)
            
            doc.save(full_path, garbage=4, deflate=True)
            doc.close()
            # messagebox.showinfo("Success", "Labels generated successfully!")
            
            # Auto-open
            try:
                os.startfile(full_path)
            except Exception:
                import webbrowser
                webbrowser.open(full_path)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate PDF: {e}")
        
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

        default_folder_frame = tk.Frame(file_frame)
        default_folder_frame.pack(fill='x', pady=(10, 0))

        tk.Label(default_folder_frame, text="Default Output Folder:",
                font=('Segoe UI', 9, 'bold')).pack(anchor='w')

        default_folder_entry_frame = tk.Frame(default_folder_frame)
        default_folder_entry_frame.pack(fill='x', pady=(5, 0))

        self.default_output_dir_entry = ttk.Entry(default_folder_entry_frame,
                                                  textvariable=self.default_output_dir,
                                                  font=('Segoe UI', 9),
                                                  state='readonly')
        self.default_output_dir_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ttk.Button(default_folder_entry_frame, text="Browse Folder",
                  command=lambda: self.browse_default_output_folder(self.default_output_dir)).pack(side='right')
        
    def create_controls_section(self, parent):
        """Create control buttons section"""
        controls_frame = tk.Frame(parent, bg=self.colors['bg_primary'])
        controls_frame.pack(fill='x', pady=(0, 15))
        # Toggle for 4x4 labels (crop bottom 50mm)
        self.label_toggle = ttk.Checkbutton(controls_frame, text="4X4 label",
                                            variable=self.is_4x4_var)
        self.label_toggle.pack(side='left', padx=(0, 10))

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
            self.set_default_output_path(filename, self.output_file_path, self.default_output_dir,
                                         "label_processor", "_processed")
            self.log_message(f"Input file selected: {os.path.basename(filename)}")
            
    def browse_output_file(self):
        filename = filedialog.asksaveasfilename(
            title="Save Processed PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            self.output_file_path.set(filename)
            folder_path = os.path.dirname(filename)
            if folder_path:
                self.default_output_dir.set(folder_path)
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
                                args=(input_path, output_path, self.is_4x4_var.get()))
        thread.daemon = True
        thread.start()
    
    # Include all the optimized processing methods
    def format_product_label(self, product_name: str, qty: int = 1) -> str:
        """Return the compact family marker used for page labeling.

        Examples:
            "OIL", "OILX2", "POTLI", "POTLIX2", "ROLLONX3"
        """
        family = str(product_name).strip().upper()
        if family == "UNKNOWN PRODUCT":
            return family if qty <= 1 else f"{family}X{qty}"

        if qty > 1:
            return f"{family}X{qty}"
        return family

    def get_qty_from_label(self, label_text: str) -> int:
        """Extract quantity from compact product labels like OILX2 or POTLIX3."""
        match = re.search(r'X(\d+)$', str(label_text).strip().upper())
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return 1
        return 1

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
                if "x" in label_text or len(skus_on_page) > 1:
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
            raw = label.replace('→ ', '').strip().upper()
            normalized = raw.replace(' ', '')

            # detect trailing quantity marker like X2, X3
            qty = 1
            m = __import__('re').search(r'X(\d+)$', normalized)
            if m:
                try:
                    qty = int(m.group(1))
                except ValueError:
                    qty = 1

            # Oil family (catch names like 'Tulir Naturals Oil 100ml')
            if 'OIL' in normalized:
                if qty == 1:
                    return (1, normalized)
                if qty == 2:
                    return (2, normalized)
                if qty == 3:
                    return (3, normalized)
                return (4, normalized)

            # Potli family
            if 'POTLI' in normalized:
                if qty == 1:
                    return (5, normalized)
                if qty == 2:
                    return (6, normalized)
                if qty == 3:
                    return (7, normalized)
                return (8, normalized)

            # Rollon family
            if 'ROLLON' in normalized:
                if qty == 1:
                    return (9, normalized)
                if qty == 2:
                    return (10, normalized)
                return (11, normalized)

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
        
    def _process_pdf_thread(self, input_path, output_path, crop_bottom_enabled=False):
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

                label_text = " | ".join([label for _, label in sku_labels])
                marked_pages.append((i, label_text))
                
                oil_counts, potli_counts = self.count_products(sku_labels)
                for k, v in oil_counts.items():
                    total_oil_counts[k] += v
                for k, v in potli_counts.items():
                    total_potli_counts[k] += v
            
            self.display_statistics(total_oil_counts, total_potli_counts, marked_pages, unmarked_pages)
            
            # Process special SKUs logic
            final_page_order = marked_pages.copy()
            all_skipped_special_skus = defaultdict(list)
            
            for i, label_text in marked_pages:
                sku = label_text.split('→')[-1].strip()
                if sku in ["TN0001", "TS-NLT5-CZ47"]:
                    final_labels, skipped_special_skus = self.process_special_skus(marked_pages, i)
                    final_page_order = [(i, lbl) for i, lbl in final_page_order if i not in skipped_special_skus]
                    final_page_order.insert(0, (i, final_labels[0]))  # Prioritize the special SKU label
                    all_skipped_special_skus.update(skipped_special_skus)
            
            # Group remaining pages
            grouped_order = self.group_pages_optimized(final_page_order, unmarked_pages, all_skipped_special_skus)
            
            self.log_message("Creating final PDF...")
            new_doc = fitz.open()
            
            for page_num, label_text in grouped_order:
                new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                if label_text:
                    page = new_doc[-1]
                    page.insert_text(
                        fitz.Point(5, 250),
                        label_text,
                        fontname="Courier-Bold",
                        fontsize=12,
                        color=(1, 0, 0)
                    )
            
            # Handle cropping for 4x4 labels
            if crop_bottom_enabled and len(grouped_order) > 0:
                self.log_message("Cropping bottom 50mm for 4x4 label...")
                for i, (page_num, _) in enumerate(grouped_order):
                    if i < len(grouped_order) - 1:  # Don't crop the last page
                        page = new_doc[i]
                        rect = page.rect
                        # Crop 50mm from the bottom
                        crop_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1 - 50 * fitz.mupdf.PIXELSPERMILLIMETER)
                        page.set_cropbox(crop_rect)
            
            new_doc.save(output_path)
            new_doc.close()
            doc.close()
            
            self.log_message("PDF processing completed successfully!")
            self.root.after(0, self.processing_complete, output_path)
        
        except Exception as e:
            self.log_message(f"ERROR: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to process PDF: {e}"))
            self.process_button.config(state="normal", text="Process PDF")
            self.open_pdf_button.config(state="disabled")
    
    def processing_complete(self, output_path):
        self.process_button.config(state="normal", text="Process PDF")
        if os.path.exists(output_path):
            self.open_pdf_button.config(state="normal")
            messagebox.showinfo("Success", f"PDF processed successfully!\n\nOutput saved to:\n{output_path}")
        else:
            self.open_pdf_button.config(state="disabled")
    
    def open_converted_pdf(self):
        output_path = self.output_file_path.get()
        if output_path and os.path.exists(output_path):
            try:
                self.log_message("Opening converted PDF...")
                os.startfile(output_path)
            except Exception as e:
                error_msg = f"Could not open PDF: {e}"
                self.log_message(error_msg)
                messagebox.showerror("Error", error_msg)
        else:
            messagebox.showerror("Error", "Converted PDF not found.")
    
    def browse_st_input_file(self):
        file_path = filedialog.askopenfilename(
            title="Select ST Input PDF File",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.st_input_file_path.set(file_path)
            self.set_default_output_path(file_path, self.st_output_file_path,
                                         self.st_default_output_dir,
                                         "st_courier", "_ST_processed")
    
    def browse_st_output_file(self):
        file_path = filedialog.asksaveasfilename(
            title="Save ST Processed PDF",
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_path:
            self.st_output_file_path.set(file_path)
            folder_path = os.path.dirname(file_path)
            if folder_path:
                self.st_default_output_dir.set(folder_path)


def main():
    """Launch the Shiprocket Label Processor GUI."""
    root = tk.Tk()
    app = WindowsStylePDFProcessor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
