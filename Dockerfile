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

RUN pip install --no-cache-dir --upgrade pip
# Install the project dependencies
RUN python -m ensurepip --upgrade
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY ./krr.py krr.py
COPY ./robusta_krr/ robusta_krr/
COPY ./intro.txt intro.txt

# Remove unused OS packages with unfixed CVEs (perl-base: 4 CRITICAL; util-linux
# family: HIGH). dpkg exits non-zero on essential-package warnings even on
# success, so removals and runtime sanity are verified explicitly instead.
RUN dpkg --purge --force-remove-essential --force-depends \
      perl-base \
      util-linux bsdutils mount \
      libmount1 libblkid1 libsmartcols1 liblastlog2-2 libuuid1 \
    ; rm -rf /var/lib/apt/lists/* \
    && for p in perl-base util-linux bsdutils mount libmount1 libblkid1 \
                libsmartcols1 liblastlog2-2 libuuid1; do \
         if dpkg -l "$p" 2>/dev/null | grep -q '^[hi]i'; then \
           echo "ERROR: $p was not removed" >&2; exit 1; \
         fi; \
       done \
    && python -c "import robusta_krr" \
    && python -c "import uuid; uuid.uuid4(); uuid.uuid1(); uuid.getnode()" \
    && bash -c 'echo bash-ok' \
    && echo "purge verified"

# Run the application using 'poetry run krr simple'
CMD ["python", "krr.py", "simple"]
