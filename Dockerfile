FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080

WORKDIR /app

# Copy all project files into container
COPY . /app/

# Install dependencies (detects either root requirements.txt or weather_agent/requirements.txt)
RUN if [ -f /app/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/requirements.txt; \
    elif [ -f /app/weather_agent/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/weather_agent/requirements.txt; \
    else \
        pip install --no-cache-dir "google-adk[a2a]" "a2a-sdk[http-server]>=0.3.20,<0.4.0" uvicorn fastapi python-dotenv google-auth; \
    fi

# Set Python path to find root and agent packages
ENV PYTHONPATH=/app

EXPOSE 8080

# Start the Weather Agent A2A server
CMD ["sh", "-c", "if [ -f /app/weather_agent/main.py ]; then python /app/weather_agent/main.py; else python /app/main.py; fi"]
