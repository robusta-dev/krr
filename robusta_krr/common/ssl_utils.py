"""Utilities for handling custom SSL certificates."""

import base64
import os

import certifi

CUSTOM_CERTIFICATE_PATH = "/tmp/custom_ca.pem"


def append_custom_certificate(custom_ca: str) -> None:
    """Append a custom CA certificate to the certifi CA bundle."""
    with open(certifi.where(), "ab") as outfile:
        outfile.write(base64.b64decode(custom_ca))

    os.environ["WEBSOCKET_CLIENT_CA_BUNDLE"] = certifi.where()


def create_temporary_certificate(custom_ca: str) -> None:
    """Create a temporary certificate file combining certifi CA bundle with a custom CA."""
    with open(certifi.where(), "rb") as base_cert:
        base_cert_content = base_cert.read()

    with open(CUSTOM_CERTIFICATE_PATH, "wb") as outfile:
        outfile.write(base_cert_content)
        outfile.write(base64.b64decode(custom_ca))

    os.environ["REQUESTS_CA_BUNDLE"] = CUSTOM_CERTIFICATE_PATH
    os.environ["WEBSOCKET_CLIENT_CA_BUNDLE"] = CUSTOM_CERTIFICATE_PATH
    certifi.where = lambda: CUSTOM_CERTIFICATE_PATH


def add_custom_certificate(custom_ca: str) -> bool:
    """Add a custom CA certificate, falling back to a temporary file on permission errors."""
    if not custom_ca:
        return False

    # NOTE: Sometimes (Openshift) the certifi.where() is not writable, so we need to
    #       use a temporary file in case of PermissionError.
    try:
        append_custom_certificate(custom_ca)
    except PermissionError:
        create_temporary_certificate(custom_ca)

    return True
