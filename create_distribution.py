#!/usr/bin/env python3
"""
Create Distribution Package
Creates the final distribution package from the built application.
"""

import os
import shutil
from pathlib import Path

def create_distribution_package():
    """Create a complete distribution package."""
    print("Creating distribution package...")
    
    # Create dist directory structure
    dist_dir = Path("dist/PDF_Label_Processor_Distribution")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy executable (for Windows, this would be .exe)
    if os.path.exists("dist/PDF_Label_Processor"):
        shutil.copy("dist/PDF_Label_Processor", dist_dir)
        print("✓ Copied executable")
    
    # Copy documentation
    for doc_file in ["README.md", "GUI_README.md", "README_Windows.md"]:
        if os.path.exists(doc_file):
            shutil.copy(doc_file, dist_dir)
            print(f"✓ Copied {doc_file}")
    
    # Copy installer
    if os.path.exists("install.bat"):
        shutil.copy("install.bat", dist_dir)
        print("✓ Copied installer")
    
    # Create zip file
    try:
        shutil.make_archive("PDF_Label_Processor_Windows", 'zip', dist_dir)
        print("✓ Created distribution ZIP file")
        return True
    except Exception as e:
        print(f"✗ Failed to create ZIP: {e}")
        return False

if __name__ == "__main__":
    create_distribution_package() 