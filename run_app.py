"""
MedSight Application Launcher

Run this script to start the MedSight application.
Usage: streamlit run run_app.py
"""

import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the main app
from src.ui.app import main

if __name__ == "__main__":
    main()
