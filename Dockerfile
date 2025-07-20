# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY ./core/requirements.txt /app/core/requirements.txt
RUN pip install --no-cache-dir -r /app/core/requirements.txt

# Copy the service account file so the app can access it
COPY ./airy-totality-465918-i2-ca296b2fa7a2.json /app/core/

# Copy the rest of the application code
COPY ./core /app/core

# Set the working directory to the core folder
WORKDIR /app/core

# Command to run the application
CMD ["python", "main.py"]
