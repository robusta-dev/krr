FROM python:3.15-alpine
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


# Drop pip after installing: it vendors setuptools 70.3.0 (CVE-2025-47273)
# and the enforcer never calls pip at runtime.
RUN pip install --no-cache-dir "pip>=25.3" \
    && rm -rf /usr/local/lib/python3.12/ensurepip/_bundled/pip-*.whl \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip

CMD ["python", "enforcer_main.py"]
