# Use the official Python 3.12 slim image as the base image
FROM python:3.12-slim AS builder
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# Install system dependencies required for Poetry
RUN apt-get update && \
    dpkg --add-architecture arm64

# Upgrade libattr1 and libacl1 to the fixed versions (CVE-2026-54371 in
# attr < 2.6.0; CVE-2026-54369 and CVE-2026-54370 in acl < 2.4.0). Trixie has
# no fixed build yet (fix arrives only in a future point release), so these
# two leaf libraries are pulled from unstable, pinned low so that nothing
# else is upgraded from there.
RUN echo 'deb http://deb.debian.org/debian unstable main' > /etc/apt/sources.list.d/unstable.list \
    && printf 'Package: *\nPin: release a=unstable\nPin-Priority: 100\n' > /etc/apt/preferences.d/unstable \
    && apt-get update \
    && apt-get install -y --no-install-recommends -t unstable libattr1 libacl1 \
    && rm /etc/apt/sources.list.d/unstable.list /etc/apt/preferences.d/unstable \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libattr1)" ge 1:2.6.0 \
    && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' libacl1)" ge 2.4.0

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
