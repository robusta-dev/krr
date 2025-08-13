FROM python:3.12-alpine
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# Patching CVE-2025-6965
RUN apk update && apk add --no-cache --upgrade \
    sqlite-libs=3.49.2-r1 sqlite=3.49.2-r1
    
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
