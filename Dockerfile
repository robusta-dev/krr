# Use the official Python 3.9 slim image as the base image
FROM us-central1-docker.pkg.dev/genuine-flight-317411/devel/base/python3.12-dev as builder
ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/venv/bin:$PATH"

# Set the working directory
WORKDIR /app

COPY ./requirements.txt requirements.txt

RUN pip install --upgrade pip
# Install the project dependencies
RUN python -m ensurepip --upgrade
RUN pip install -r requirements.txt

FROM us-central1-docker.pkg.dev/genuine-flight-317411/devel/base/python3.12
# Copy the rest of the application code
COPY . .
COPY --from=builder /app/venv /venv

# Run the application using 'poetry run krr simple'
CMD ["python", "krr.py", "simple"]
