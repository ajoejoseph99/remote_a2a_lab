FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080

WORKDIR /app

# Install dependencies
COPY weather_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY weather_agent/ /app/weather_agent/

# Set Python path to find weather_agent package
ENV PYTHONPATH=/app

# Expose Cloud Run port
EXPOSE 8080

# Start the A2A server
CMD ["python", "weather_agent/main.py"]
