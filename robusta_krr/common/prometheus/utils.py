from requests.sessions import merge_setting

from ..prometheus.auth import PrometheusAuthorization
from ..prometheus.custom_connect import AWSPrometheusConnect, CustomPrometheusConnect
from ..prometheus.models import AWSPrometheusConfig, PrometheusConfig
from collections import defaultdict
from typing import List, Dict
from urllib.parse import parse_qs

def parse_query_string(query_string: str) -> Dict[str, List[str]]:
    if not query_string:
        return {}
    query_params = parse_qs(query_string, keep_blank_values=True)
    parsed_params = defaultdict(list)

    for key, values in query_params.items():
        for value in values:
            parsed_params[key].append(value)

    return parsed_params

def get_custom_prometheus_connect(prom_config: PrometheusConfig) -> "CustomPrometheusConnect":
    prom_config.headers.update(PrometheusAuthorization.get_authorization_headers(prom_config))
    if isinstance(prom_config, AWSPrometheusConfig):
        prom = AWSPrometheusConnect(
            access_key=prom_config.access_key,
            secret_key=prom_config.secret_access_key,
            service_name=prom_config.service_name,
            region=prom_config.aws_region,
            config=prom_config,
        )
    else:
        prom = CustomPrometheusConnect(config=prom_config)

    if prom_config.prometheus_url_query_string:
        query_string_params = parse_query_string(prom_config.prometheus_url_query_string)
        prom._session.params = merge_setting(prom._session.params, query_string_params)
    prom.config = prom_config
    return prom
