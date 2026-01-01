FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if needed (e.g. for PDF processing, OpenCV)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpoppler-cpp-dev \
    pkg-config \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Expose Streamlit port
EXPOSE 8080

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Run the application
CMD ["streamlit", "run", "src/ui/app.py", "--server.port=8080", "--server.address=0.0.0.0"]
