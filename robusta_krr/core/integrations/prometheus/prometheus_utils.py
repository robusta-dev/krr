from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
from prometrix import AWSPrometheusConfig, CoralogixPrometheusConfig, PrometheusConfig, VictoriaMetricsPrometheusConfig

from robusta_krr.core.models.config import settings

if TYPE_CHECKING:
    from robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service import (
        PrometheusMetricsService,
    )


class ClusterNotSpecifiedException(Exception):
    """
    An exception raised when a prometheus requires a cluster label but an invalid one is provided.
    """

    pass


def generate_prometheus_config(
    url: str, headers: dict[str, str], metrics_service: PrometheusMetricsService
) -> PrometheusConfig:
    from .metrics_service.victoria_metrics_service import VictoriaMetricsService

    baseconfig = {
        "url": url,
        "disable_ssl": not settings.prometheus_ssl_enabled,
        "headers": headers,
    }

    # aws config
    if settings.eks_managed_prom:
        session = boto3.Session(profile_name=settings.eks_managed_prom_profile_name)
        credentials = session.get_credentials()
        region = settings.eks_managed_prom_region if settings.eks_managed_prom_region else session.region_name

        if settings.eks_access_key and settings.eks_secret_key:
            # when we have both access key and secret key, don't try to read credentials which can fail
            access_key = settings.eks_access_key
            secret_key = settings.eks_secret_key.get_secret_value()
        else:
            # we need at least one parameter from credentials, but we should use whatever we can from settings (this has higher precedence)
            credentials = credentials.get_frozen_credentials()
            access_key = settings.eks_access_key if settings.eks_access_key else credentials.access_key
            secret_key = settings.eks_secret_key.get_secret_value() if settings.eks_secret_key else credentials.secret_key
        
        service_name = settings.eks_service_name if settings.eks_secret_key else "aps"
        if not region:
            raise Exception("No eks region specified")

        return AWSPrometheusConfig(
            access_key=access_key,
            secret_access_key=secret_key,
            aws_region=region,
            service_name=service_name,
            **baseconfig,
        )
    # coralogix config
    if settings.coralogix_token:
        return CoralogixPrometheusConfig(**baseconfig, prometheus_token=settings.coralogix_token.get_secret_value())
    if isinstance(metrics_service, VictoriaMetricsService):
        return VictoriaMetricsPrometheusConfig(**baseconfig)
    return PrometheusConfig(**baseconfig)
