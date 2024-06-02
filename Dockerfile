# Use the official Python 3.9 slim image as the base image
FROM python:3.12-slim as builder
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# Set the working directory
WORKDIR /app

COPY ./requirements.txt requirements.txt

RUN pip install --upgrade pip
# Install the project dependencies
RUN python -m ensurepip --upgrade
RUN pip install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run the application using 'poetry run krr simple'
CMD ["python", "krr.py", "simple"]
