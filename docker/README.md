# Dockerfiles for specific clouds

This directory will include Dockerfiles for various cloud providers.

## AWS

For the usage of `krr` container we need the Dockerfile to have `awscli` installed on it.
The `aws.Dockerfile` is a modified `krr` dockerfile which includes:
  -  installation of curl & zip
  -  installation of awscli


