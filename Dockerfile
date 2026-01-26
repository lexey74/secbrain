FROM python:3.12-slim

# Install system dependencies
# ffmpeg - required for audio/video processing
# curl - for healthchecks or downloading helpers if needed
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ensure data directories exist (placeholder, actual data comes from volumes)
RUN mkdir -p /app/data/inbox /app/data/temp /app/data/config /app/logs

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Environment variables defaults
ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data
ENV LOG_LEVEL=INFO

# Run command
# Using python directly. For production, consider using a process manager or array syntax.
CMD ["python", "server_mcp.py"]