# Use the official Python 3.9 slim image as the base image
FROM cgr.dev/chainguard/python:latest-dev as builder
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"
RUN pip install --upgrade pip
# these take a long time to build
RUN pip install matplotlib==3.8.4
RUN pip install pandas==2.2.2