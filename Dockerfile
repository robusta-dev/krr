# Use the official Python 3.12 slim image as the base image
FROM python:3.12-slim AS builder
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# Install system dependencies required for Poetry
RUN apt-get update && \
    dpkg --add-architecture arm64

# Set the working directory
WORKDIR /app

COPY ./requirements.txt requirements.txt

COPY ./krr.py krr.py
COPY ./robusta_krr/ robusta_krr/
COPY ./intro.txt intro.txt

RUN pip install -r requirements.txt pyinstaller && \
    apt-get update -q && apt-get install -y binutils wget && \
    pyinstaller --onefile krr.py

RUN mv ./dist/krr /usr/local/bin/krr && \
    chmod a+x /usr/local/bin/krr

RUN wget -nv "https://dl.k8s.io/release/v1.23.3/bin/linux/amd64/kubectl"  && \
    mv kubectl /usr/local/bin/kubectl && \
    chmod a+x /usr/local/bin/kubectl


# RUN pip install --no-cache-dir --upgrade pip
# # Install the project dependencies
# RUN python -m ensurepip --upgrade
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy the rest of the application code
# COPY ./krr.py krr.py
# COPY ./robusta_krr/ robusta_krr/
# COPY ./intro.txt intro.txt

# # Run the application using 'poetry run krr simple'
# CMD ["python", "krr.py", "simple"]
