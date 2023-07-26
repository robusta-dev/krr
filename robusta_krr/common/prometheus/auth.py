import logging
import os
from typing import Dict

import requests

from ..prometheus.models import (
    AzurePrometheusConfig,
    CoralogixPrometheusConfig,
    PrometheusConfig,
)


class PrometheusAuthorization:
    bearer_token: str = ""
    azure_authorization: bool = (
        os.environ.get("AZURE_CLIENT_ID", "") != "" and os.environ.get("AZURE_TENANT_ID", "") != ""
    ) and (os.environ.get("AZURE_CLIENT_SECRET", "") != "" or os.environ.get("AZURE_USE_MANAGED_ID", "") != "")

    @classmethod
    def get_authorization_headers(cls, config: PrometheusConfig) -> Dict:
        if isinstance(config, CoralogixPrometheusConfig):
            return {"token": config.prometheus_token}
        elif config.prometheus_auth:
            return {"Authorization": config.prometheus_auth.get_secret_value()}
        elif cls.azure_authorization:
            return {"Authorization": (f"Bearer {cls.bearer_token}")}
        else:
            return {}

    @classmethod
    def request_new_token(cls, config: PrometheusConfig) -> bool:
        if cls.azure_authorization and isinstance(config, AzurePrometheusConfig):
            try:
                if config.azure_use_managed_id:
                    res = requests.get(
                        url=config.azure_metadata_endpoint,
                        headers={
                            "Metadata": "true",
                        },
                        data={
                            "api-version": "2018-02-01",
                            "client_id": config.azure_client_id,
                            "resource": config.azure_resource,
                        },
                    )
                else:
                    res = requests.post(
                        url=config.azure_token_endpoint,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        data={
                            "grant_type": "client_credentials",
                            "client_id": config.azure_client_id,
                            "client_secret": config.azure_client_secret,
                            "resource": config.azure_resource,
                        },
                    )
            except Exception:
                logging.exception("Unexpected error when trying to generate azure access token.")
                return False

            if not res.ok:
                logging.error(f"Could not generate an azure access token. {res.reason}")
                return False

            cls.bearer_token = res.json().get("access_token")
            logging.info("Generated new azure access token.")
            return True

        return False
