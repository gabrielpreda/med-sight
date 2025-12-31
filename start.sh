#!/bin/bash

# MedSight Quick Start Script
# This script helps you get started with MedSight

echo "🏥 MedSight v2.0 - Quick Start"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade pip
echo ""
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install package in development mode
echo ""
echo "📦 Installing MedSight in development mode..."
pip install -e .

# Check if .env exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  WARNING: .env file not found!"
    echo "Please create a .env file with your Google Cloud credentials:"
    echo ""
    echo "PROJECT_ID=your-project-id"
    echo "REGION=us-central1"
    echo "ENDPOINT_ID=your-endpoint-id"
    echo "ENDPOINT_REGION=us-central1"
    echo ""
    read -p "Press Enter to continue..."
fi

# Run the application
echo ""
echo "🚀 Starting MedSight..."
echo ""
streamlit run run_app.py

# Deactivate on exit
deactivate
