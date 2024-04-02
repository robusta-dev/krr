from typing import Optional

from robusta_krr.core.models.config import settings

# NOTE: This one should be mounted if openshift is enabled (done by Robusta Runner)
TOKEN_LOCATION = '/var/run/secrets/kubernetes.io/serviceaccount/token'


def load_token() -> Optional[str]:
    if not settings.openshift:
        return None

    try:
        with open(TOKEN_LOCATION, 'r') as file:
            return file.read()
    except FileNotFoundError:
        return None
