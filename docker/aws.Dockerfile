# Use the official Python 3.9 slim image as the base image
FROM python:3.9-slim as builder

# Set the working directory
WORKDIR /app

# Install system dependencies required for Poetry
RUN apt-get update && \
    dpkg --add-architecture arm64

COPY ./requirements.txt requirements.txt

# Install the project dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install curl and unzip for awscli 
RUN apt-get -y update; apt-get -y install curl; apt-get -y install unzip

# Download awscli and unzip it
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
	./aws/install

# Copy the rest of the application code
COPY . .

# Run the application using 'poetry run krr simple'
ENTRYPOINT ["python", "krr.py", "simple"]
