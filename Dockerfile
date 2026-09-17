# Use the official Python 3.12 slim image as the base image
FROM python:3.12-slim AS builder
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# Pull in all pending Debian security updates (e.g. openssl/libssl3t64
# 3.5.7-1~deb13u2, which fixes the CVEs reported against 3.5.6-1~deb13u2).
# The base image is only rebuilt periodically, so without this step the image
# ships whatever package versions the base happened to be built with.
RUN apt-get update && \
    apt-get dist-upgrade -y --no-install-recommends && \
    dpkg --add-architecture arm64 && \
    dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libssl3t64)" ge 3.5.7-1~deb13u2

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
# family: HIGH). Also remove libattr1/libacl1 (CVE-2026-54371, CVE-2026-54369,
# CVE-2026-54370): trixie has no fixed version, so scanners flag *any* installed
# version, even the fixed sid build. The vulnerable code lives in the
# getfattr/setfattr/setfacl binaries, which were never installed; only the shared
# libraries were, pulled in by coreutils/tar/sed/passwd, so those go too. This
# leaves the runtime image without ls/cat/cp/tar/sed (python and bash remain).
# dpkg exits non-zero on essential-package warnings even on success, so removals
# and runtime sanity are verified explicitly instead.
RUN rm -rf /var/lib/apt/lists/* \
    ; dpkg --purge --force-remove-essential --force-depends passwd \
    ; dpkg --purge --force-remove-essential --force-depends \
      perl-base \
      util-linux bsdutils mount \
      libmount1 libblkid1 libsmartcols1 liblastlog2-2 libuuid1 \
      tar sed coreutils libacl1 libattr1 \
    ; dpkg --clear-avail \
    ; for p in perl-base util-linux bsdutils mount libmount1 libblkid1 \
                libsmartcols1 liblastlog2-2 libuuid1 \
                passwd tar sed coreutils libacl1 libattr1; do \
         status="$(dpkg-query -W -f='${db:Status-Status}' "$p" 2>/dev/null || true)"; \
         if [ -n "$status" ] && [ "$status" != "not-installed" ]; then \
           echo "ERROR: $p was not removed (status: $status)" >&2; exit 1; \
         fi; \
       done \
    && python -c "import robusta_krr" \
    && python -c "import uuid; uuid.uuid4(); uuid.uuid1(); uuid.getnode()" \
    && bash -c 'echo bash-ok' \
    && echo "purge verified"

# Run the application using 'poetry run krr simple'
CMD ["python", "krr.py", "simple"]
