FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway uses $PORT environment variable)
EXPOSE $PORT

# Run the simple application with PORT from environment
CMD uvicorn app.simple_auth_main:app --host 0.0.0.0 --port $PORT