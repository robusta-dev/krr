import os

from robusta_krr.common.ssl_utils import add_custom_certificate

ADDITIONAL_CERTIFICATE: str = os.environ.get("CERTIFICATE", "")

if add_custom_certificate(ADDITIONAL_CERTIFICATE):
    print("added custom certificate")

# DO NOT ADD ANY CODE ABOVE THIS
# ADDING IMPORTS BEFORE ADDING THE CUSTOM CERTS MIGHT INIT HTTP CLIENTS THAT DOESN'T RESPECT THE CUSTOM CERT

from robusta_krr import run

if __name__ == "__main__":
    run()
