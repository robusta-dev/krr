"""Patches for the Kubernetes client to support proxy-url in kubeconfig."""

# NOTE: This is a workaround for the issue described here:
# https://github.com/kubernetes-client/python/pull/1863

from __future__ import annotations

from typing import Optional

from kubernetes.client import configuration
from kubernetes.config import kube_config


class KubeConfigLoader(kube_config.KubeConfigLoader):
    """Extended KubeConfigLoader that adds proxy-url support."""
    def _load_cluster_info(self):
        """Load cluster info and extract proxy-url if present."""
        super()._load_cluster_info()

        if "proxy-url" in self._cluster:
            self.proxy = self._cluster["proxy-url"]

    def _set_config(self, client_configuration: Configuration):
        """Set client configuration including proxy settings."""
        super()._set_config(client_configuration)

        key = "proxy"
        if key in self.__dict__:
            setattr(client_configuration, key, getattr(self, key))


class Configuration(configuration.Configuration):
    """Extended Kubernetes Configuration with proxy support."""
    def __init__(
        self,
        proxy: Optional[str] = None,
        **kwargs,
    ):
        """Initialize Configuration with optional proxy setting."""
        super().__init__(**kwargs)

        self.proxy = proxy


configuration.Configuration = Configuration
kube_config.KubeConfigLoader = KubeConfigLoader
