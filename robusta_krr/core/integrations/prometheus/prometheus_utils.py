from robusta_krr.common.prometheus.models import PrometheusConfig, CoralogixPrometheusConfig, AWSPrometheusConfig, VictoriaMetricsPrometheusConfig
from robusta_krr.core.models.config import Config
import boto3

class ClusterNotSpecifiedException(Exception):
    """
    An exception raised when a prometheus requires a cluster label but an invalid one is provided.
    """

    pass

def generate_prometheus_config(config: Config, url: str, headers: dict[str, str], is_victoria_metrics: bool = False) -> PrometheusConfig:
    baseconfig = {
        "url": url,
        "disable_ssl": not config.prometheus_ssl_enabled,
        "headers": headers,
    }

    # aws config
    if config.eks_managed_prom:
        session = boto3.Session(profile_name=config.eks_managed_prom_profile_name)
        credentials = session.get_credentials()
        credentials = credentials.get_frozen_credentials()
        region = config.eks_managed_prom_region if config.eks_managed_prom_region else session.region_name
        access_key = config.eks_access_key if config.eks_access_key else credentials.access_key
        secret_key = config.eks_secret_key if config.eks_secret_key else credentials.secret_key
        service_name = config.eks_service_name if config.eks_secret_key else "aps"
        if not region:
            raise Exception("No eks region specified")

        return AWSPrometheusConfig(
            access_key=access_key,
            secret_access_key=secret_key,
            aws_region= region,
            service_name=service_name,
            **baseconfig,
        )
    # coralogix config
    if config.coralogix_token:
        return CoralogixPrometheusConfig(**baseconfig, prometheus_token=config.coralogix_token)
    if is_victoria_metrics:
        return VictoriaMetricsPrometheusConfig(**baseconfig)
    return PrometheusConfig(**baseconfig)