# NOTE: This is a workaround for the issue described here:
# https://github.com/kubernetes-client/python/pull/1863

from __future__ import annotations

from typing import Optional

from kubernetes.client import configuration
from kubernetes.config import kube_config


class KubeConfigLoader(kube_config.KubeConfigLoader):
    def _load_cluster_info(self):
        super()._load_cluster_info()

        if "proxy-url" in self._cluster:
            self.proxy = self._cluster["proxy-url"]

        # Support tls-server-name for Teleport and similar proxies
        # See: https://github.com/robusta-dev/krr/issues/495
        if "tls-server-name" in self._cluster:
            self.tls_server_name = self._cluster["tls-server-name"]

    def _set_config(self, client_configuration: Configuration):
        super()._set_config(client_configuration)

        for key in ("proxy", "tls_server_name"):
            if key in self.__dict__:
                setattr(client_configuration, key, getattr(self, key))


class Configuration(configuration.Configuration):
    def __init__(
        self,
        proxy: Optional[str] = None,
        tls_server_name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.proxy = proxy
        self.tls_server_name = tls_server_name


configuration.Configuration = Configuration
kube_config.KubeConfigLoader = KubeConfigLoader
