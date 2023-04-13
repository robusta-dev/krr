# Use the official Python 3.9 slim image as the base image
FROM python:3.9-slim as builder

# Set the working directory
WORKDIR /app

# Install system dependencies required for Poetry
RUN apt-get update && \
    apt-get install --no-install-recommends -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python -

# Add Poetry to the PATH
ENV PATH="/root/.local/bin:${PATH}"

# Copy the pyproject.toml files
COPY pyproject.toml ./

# Install the project dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi --no-root

# Copy the rest of the application code
COPY . .

# Run the application using 'poetry run krr simple'
CMD ["python", "krr.py", "simple"]
