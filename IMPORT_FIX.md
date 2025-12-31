# Import Error Fix - MedSight v2.0

## Problem
When running `streamlit run src/ui/app.py`, you get:
```
ModuleNotFoundError: No module named 'src'
```

## Root Cause
Python couldn't find the `src` module because it wasn't in the Python path when running from the nested directory structure.

## ✅ Solutions (Choose One)

### **Solution 1: Use the Launcher Script (RECOMMENDED)**

I've created a launcher script at the project root. Simply run:

```bash
streamlit run run_app.py
```

This automatically sets up the Python path correctly.

---

### **Solution 2: Install as Development Package (BEST for Development)**

Install MedSight as an editable package:

```bash
# From the project root
pip install -e .
```

Then run:
```bash
streamlit run run_app.py
```

---

### **Solution 3: Use the Quick Start Script (EASIEST)**

I've created an automated setup script:

```bash
# Make it executable (first time only)
chmod +x start.sh

# Run it
./start.sh
```

This script will:
- Create virtual environment if needed
- Install all dependencies
- Install MedSight in development mode
- Start the application

---

### **Solution 4: Set PYTHONPATH (Manual)**

If you prefer to run directly from src/ui/app.py:

```bash
# From project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
streamlit run src/ui/app.py
```

---

## ✅ What I Fixed

1. **Updated `src/ui/app.py`**: Added path manipulation to find the src module
2. **Created `run_app.py`**: Launcher script at project root
3. **Created `setup.py`**: Makes MedSight installable as a package
4. **Created `start.sh`**: Automated setup and launch script

---

## 🚀 Recommended Workflow

### First Time Setup:
```bash
# Option A: Use the automated script
./start.sh

# Option B: Manual setup
python -m venv venv
source venv/bin/activate  # On Mac/Linux
pip install -e .
streamlit run run_app.py
```

### Subsequent Runs:
```bash
# Activate your virtual environment
source venv/bin/activate

# Run the app
streamlit run run_app.py
```

---

## 📝 Quick Reference

| Command | Purpose |
|---------|---------|
| `./start.sh` | Automated setup and run |
| `pip install -e .` | Install in development mode |
| `streamlit run run_app.py` | Run the application |
| `pytest tests/ -v` | Run tests |

---

## ✅ Verification

After running any of the solutions above, you should see:

```
You can now view your Streamlit app in your browser.

Local URL: http://localhost:8501
Network URL: http://192.168.x.x:8501
```

---

## 🔧 Troubleshooting

### If you still get import errors:

1. **Check you're in the project root**:
   ```bash
   pwd
   # Should show: /Users/gabrielpreda/workspace/my_projects/med-sight
   ```

2. **Verify virtual environment is activated**:
   ```bash
   which python
   # Should show path to venv/bin/python
   ```

3. **Reinstall in development mode**:
   ```bash
   pip install -e . --force-reinstall
   ```

4. **Check Python version**:
   ```bash
   python --version
   # Should be 3.10 or higher
   ```

---

## 📦 What Gets Installed

When you run `pip install -e .`, it installs:
- All dependencies from requirements.txt
- MedSight as an editable package
- Makes `src` module importable from anywhere

---

**Status**: ✅ FIXED  
**Date**: 2025-12-31  
**Version**: 2.0.0
