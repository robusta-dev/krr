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

# Drop OS packages that krr never uses at runtime. Debian trixie ships these
# with open CVEs that have no fixed version available, so removing them is the
# only way to clear them:
#   perl-base   CVE-2026-13221, CVE-2026-42496, CVE-2026-57433, CVE-2026-8376
#               (CRITICAL), CVE-2026-42497, CVE-2026-48962, CVE-2026-57432,
#               CVE-2026-9538 (HIGH), plus 4 MEDIUM
#   util-linux  CVE-2026-53615 (HIGH), plus 2 MEDIUM, per package
# krr is a pure-Python app: the python binary links none of these, and nothing
# in the codebase shells out to perl, mount or the util-linux tools.
#
# Deliberately NOT purged, even though they also carry unfixed CVEs:
#   ncurses (CVE-2025-69720) - bash links libtinfo.so.6, so removing it leaves
#     the image with no working bash for `kubectl exec`/`docker exec` debugging
#   login (CVE-2026-53615) - dpkg protected package, cannot be removed
#
# Known, accepted degradation: removing libuuid1 disables CPython's optional
# _uuid C accelerator, so the stdlib uuid module falls back to its pure-Python
# implementation (uuid.py handles the ImportError by design). Nothing in krr
# or its dependencies uses uuid1()/generate_time_safe - the only code paths
# _uuid accelerates - and the fallback is exercised by the check below.
#
# Kubernetes is unaffected by removing mount/util-linux: volume, secret and
# configmap mounts are performed by the container runtime on the host via
# mount(2) syscalls before the container rootfs starts; the runtime never
# execs the in-image mount binary.
#
# Note this leaves apt/dpkg unusable inside the running container. dpkg exits
# non-zero on the essential-package warnings even when every removal succeeds,
# so the removals are verified explicitly instead of trusting the exit code.
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
