# Use a lightweight Python base image
FROM python:3.10-slim

# Set working directory inside the container
WORKDIR /app

# Copy the entire project to the container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r bdg_predictor/requirements.txt

# Expose the API and Frontend ports
EXPOSE 8787
EXPOSE 8000

# Start the Python AI API and the Dashboard Server
# We use a small script to run both simultaneously in the cloud
CMD ["python", "bdg_predictor/model_api_server.py"]
