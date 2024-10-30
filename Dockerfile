# Use Python 3.9 slim image
FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create fonts directory and copy font file
RUN mkdir -p /usr/share/fonts/truetype/
COPY seguiemj.ttf /usr/share/fonts/truetype/

# Expose port
EXPOSE 5000

# Command to run the application
CMD ["python", "app.py"]