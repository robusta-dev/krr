FROM python:3.12-alpine
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# Pull in all pending Alpine security updates (openssl/libssl3/libcrypto3,
# sqlite-libs for CVE-2025-6965, etc.). The base image is only rebuilt
# periodically, so without this the image ships whatever the base was built with.
RUN apk update && apk upgrade --no-cache \
    && apk add --no-cache --upgrade sqlite-libs sqlite libssl3 libcrypto3

# Set the working directory
WORKDIR /app/enforcer

COPY ./*.py .
COPY ./dal/ dal/
COPY ./resources/ resources/
COPY ./requirements.txt requirements.txt


RUN pip install --no-cache-dir "pip>=25.3" \
    && rm -rf /usr/local/lib/python3.12/ensurepip/_bundled/pip-*.whl
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "enforcer_main.py"]
