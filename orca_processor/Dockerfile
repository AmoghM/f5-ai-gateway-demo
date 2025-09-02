FROM python:3.11-slim

WORKDIR /app

# Install git for pip git dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy processor code
COPY orca_safety_processor.py .

# Expose port
EXPOSE 8001

# Run the processor
CMD ["python", "-m", "uvicorn", "orca_safety_processor:app", "--host", "0.0.0.0", "--port", "8001"]
