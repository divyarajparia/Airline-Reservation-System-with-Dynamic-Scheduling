# Use a smaller, optimized Python base image
FROM python:3.10-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only essential files first to leverage Docker caching
COPY requirements.txt .

# Install dependencies (add system dependencies if needed)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
COPY . .

# Expose port 8000
EXPOSE 8000

# Run the Flask app
CMD ["python", "app.py"]
# Run Flask app with Gunicorn
#CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
