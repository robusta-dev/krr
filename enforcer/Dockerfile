FROM python:3.12-alpine
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# Patching CVE-2025-6965 (requires sqlite >= 3.50.2)
# Alpine's current version (3.51.1-r0) already includes the fix
RUN apk update && apk add --no-cache --upgrade \
    sqlite-libs sqlite
    
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
