FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . /app/

# Set Python path to find agent packages
ENV PYTHONPATH=/app

EXPOSE 8080

# Start the Weather Agent A2A server
CMD ["python", "weather_agent/main.py"]
