FROM python:3.11-slim

# Create app directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose the port that the Flask app runs on
# Changed to 8095 at user request
EXPOSE 8095

# Set environment variables for Flask
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=8095

# Default command to run the Flask app
CMD ["flask", "run"]