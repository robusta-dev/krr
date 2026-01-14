from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Literal, Optional, Union

from kubernetes import config as k8s_config
from kubernetes.config.config_exception import ConfigException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from robusta_krr.core.abstract.strategies import StrategySettings

CUSTOM_CERTIFICATE_ENV_VAR = "CERTIFICATE"


class PercentileSelectorSettings(BaseModel):
    percentile: float = Field(None, ge=0, le=100, description="Percentile to use for the selector.")


class PrometheusSettings(BaseModel):
    url: Optional[str] = Field(None, description="Prometheus URL")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Headers for Prometheus"
    )
    auth: Optional[tuple[str, str]] = Field(
        None, description="Prometheus auth, need to be in a tuple (user, password)"
    )
    ssl_enabled: bool = Field(True, description="Prometheus SSL enabled")
    other_headers: dict[str, str] = Field(
        default_factory=dict, description="Other headers for Prometheus"
    )


class ThanoSettings(BaseModel):
    enabled: bool = Field(False, description="Enable Thanos")
    url: Optional[str] = Field(None, description="Thanos URL")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Headers for Thanos"
    )
    auth: Optional[tuple[str, str]] = Field(
        None, description="Thanos auth, need to be in a tuple (user, password)"
    )
    ssl_enabled: bool = Field(True, description="Thanos SSL enabled")


class VictoriaMetricsSettings(BaseModel):
    enabled: bool = Field(False, description="Enable Victoria Metrics")
    url: Optional[str] = Field(None, description="Victoria Metrics URL")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Headers for Victoria Metrics"
    )
    auth: Optional[tuple[str, str]] = Field(
        None,
        description="Victoria Metrics auth, need to be in a tuple (user, password)",
    )
    ssl_enabled: bool = Field(True, description="Victoria Metrics SSL enabled")


class CostSettings(BaseModel):
    cpu_cost: float = Field(0.00004, description="CPU cost per millicores hour")
    memory_cost: float = Field(0.000000001, description="Memory cost per megabyte hour")


class Settings(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    # a mapping from cluster name to its prometheus config
    prometheus_configs: dict[str, PrometheusSettings] = Field(
        default_factory=dict, description="A mapping from cluster name to its prometheus config"
    )

    # The name of the prometheus cluster to match for global prometheus config
    # The global prometheus config is prometheus settings for a single prometheus server that has data for the entire cluster
    # This is the prometheus config that will be used when connecting to a specific cluster
    prometheus_cluster_match_name: str = Field(None, description="The name of the prometheus cluster to match")

    prometheus: PrometheusSettings = Field(
        default_factory=PrometheusSettings, description="Global Prometheus settings"
    )
    thanos: ThanoSettings = Field(
        default_factory=ThanoSettings, description="Thanos settings"
    )
    victoria_metrics: VictoriaMetricsSettings = Field(
        default_factory=VictoriaMetricsSettings, description="Victoria Metrics settings"
    )
    cost: CostSettings = Field(default_factory=CostSettings, description="Cost settings")

    max_workers: int = Field(10, description="Max workers")
    namespaces: Union[list[str], Literal["*"]] = Field(
        "*", description="Namespaces to scan"
    )
    resources: Union[list[str], Literal["*"]] = Field(
        "*", description="Resources to scan"
    )
    selector: Optional[str] = Field(None, description="Selector for objects")
    cpu_min_value: int = Field(10, description="CPU min value in millicores")
    memory_min_value: int = Field(100, description="Memory min value in MB")
    history_duration: float = Field(
        336, ge=1, description="How much time back to look (in hours)"
    )
    # New fields for specific timeframe support
    start_time: Optional[datetime] = Field(
        None,
        description="Start time for the metrics query (ISO 8601 format). "
        "When provided with end_time, takes precedence over history_duration.",
    )
    end_time: Optional[datetime] = Field(
        None,
        description="End time for the metrics query (ISO 8601 format). "
        "When provided with start_time, takes precedence over history_duration.",
    )
    timeframe_duration: float = Field(
        1.25, description="Timeframe duration in hours"
    )
    step: str = Field("30s", description="Prometheus step")
    quiet: bool = Field(False, description="Quiet mode")
    log_to_stderr: bool = Field(False, description="Log to stderr")
    width: Optional[int] = Field(None, description="Width of the output")
    strategy: str = Field("simple", description="Strategy to use")
    strategy_settings: StrategySettings = Field(
        default_factory=StrategySettings, description="Strategy settings"
    )
    other_args: dict = Field(default_factory=dict, description="Other args")
    file_output: Optional[str] = Field(
        None, description="File output, if None, will print to stdout"
    )
    file_output_dynamic: bool = Field(False, description="Dynamic file output")
    slack_output: Optional[str] = Field(None, description="Slack webhook output url")
    format: str = Field("table", description="Format of the output")
    show_cluster_name: bool = Field(False, description="Show cluster name")
    verbose: bool = Field(False, description="Verbose mode")
    inside_cluster: bool = Field(False, description="Running inside cluster")
    eks_managed_prom: bool = Field(
        False, description="EKS MSP endpoint"
    )
    eks_managed_prom_region: Optional[str] = Field(
        None, description="EKS MSP endpoint region"
    )
    eks_profile_name: Optional[str] = Field(
        None, description="EKS profile name"
    )
    eks_access_key: Optional[str] = Field(
        None, description="EKS access key"
    )
    eks_secret_key: Optional[str] = Field(
        None, description="EKS secret key"
    )
    eks_service_name: Optional[str] = Field(
        None, description="EKS managed prometheus type"
    )
    coralogix_prom: bool = Field(
        False, description="Coralogix prometheus endpoint"
    )
    gcp_managed_prom: bool = Field(
        False, description="GCP managed prometheus"
    )
    azure_managed_prom: bool = Field(
        False, description="Azure Monitor managed prometheus"
    )
    openshift: bool = Field(
        False, description="OpenShift flag, if set will look for openshift prometheus"
    )
    max_retries: int = Field(
        3, description="Max retries for prometheus queries"
    )
    version: Optional[str] = Field(
        None, description="Version of the tool"
    )
    custom_schedulers: list[str] = Field(
        default_factory=lambda: ["default-scheduler"],
        description="Custom schedulers. Default pods missing a scheduler (or having a scheduler set to '')  will be treated as having `default-scheduler`",
    )
    pods_running_only: bool = Field(
        True, description="If True, will only consider running pods"
    )
    request_body_max_size: int = Field(
        512 * 1024, description="Max body size of prometheus response in kilobytes"
    )
    # If both are set, both will be used for discovering prometheus servers
    prometheus_label: Optional[str] = Field(
        None, description="Label to find prometheus pod"
    )
    prometheus_service_discovery: bool = Field(
        True, description="If true, will try to use k8s service discovery"
    )
    filter_namespaces_prefix: list[str] = Field(
        default_factory=lambda: ["openshift-", "kube-", "olm"],
        description="Namespaces to filter out by prefix",
    )
    run_per_clusters: list[str] = Field(
        default_factory=list, description="Run on specific clusters"
    )
    percentile_selector_settings: PercentileSelectorSettings = Field(
        default_factory=PercentileSelectorSettings, description="Percentile selector settings for prometheus"
    )
    use_oomkill_data: bool = Field(
        True, description="Use oomkill data"
    )
    oom_memory_buffer_percentage: int = Field(
        25, description="OOM memory buffer percentage"
    )

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_datetime(cls, value):
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # Support ISO 8601 format with various timezone notations
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(
                    f"Invalid datetime format: {value}. "
                    "Please use ISO 8601 format (e.g., '2025-09-05T10:00:00Z' or '2025-09-05T10:00:00+00:00')"
                )
        return value

    def __init__(self, **data):
        super().__init__(**data)
        self._init_kube_config()

    def _init_kube_config(self):
        try:
            k8s_config.load_incluster_config()
            self.inside_cluster = True
            logging.info("Loaded in-cluster config")
        except ConfigException:
            try:
                k8s_config.load_kube_config()
            except ConfigException as e:
                logging.warning(f"Could not load kube config: {e}")

    @staticmethod
    def init_custom_certificate():
        """
        Load a custom certificate from an environment variable into the SSL_CERT_FILE location.
        The certificate can be a raw cert, or base64 encoded.
        """
        import base64
        import certifi

        custom_certificate = os.environ.get(CUSTOM_CERTIFICATE_ENV_VAR, "")
        if custom_certificate == "":
            logging.debug("No custom certificate provided")
            return

        # make sure it has the cert begin
        if "-----BEGIN CERTIFICATE-----" not in custom_certificate:
            # try to base64 decode
            try:
                custom_certificate = base64.b64decode(custom_certificate).decode("utf-8")
            except Exception as e:
                logging.error(f"Could not decode custom certificate: {e}")

        certifi_certs_file = certifi.where()
        logging.info(f"Adding custom certificate to {certifi_certs_file}")

        with open(certifi_certs_file, "a") as f:
            f.write(custom_certificate)
