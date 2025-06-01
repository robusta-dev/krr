# Use the official Python 3.9 slim image as the base image
FROM python:3.12-slim
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# We're installing here libexpat1, to upgrade the package to include a fix to 3 high CVEs. CVE-2024-45491,CVE-2024-45490,CVE-2024-45492
RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app/enforcer

COPY ./*.py .
COPY ./dal/ dal/
COPY ./resources/ resources/
COPY ./requirements.txt requirements.txt


RUN pip install --no-cache-dir --upgrade pip
# Install the project dependencies
RUN python -m ensurepip --upgrade
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "enforcer_main.py"]
