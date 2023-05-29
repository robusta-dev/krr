# Use the official Python 3.9 slim image as the base image
FROM python:3.9-slim as builder

# Set the working directory
WORKDIR /app

# Install system dependencies required for Poetry
RUN apt-get update && \
    dpkg --add-architecture arm64

COPY ./requirements.txt requirements.txt

# Install the project dependencies
RUN pip install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run the application using 'poetry run krr simple'
CMD ["python", "krr.py", "simple"]
