# NOTE: This is a workaround for the issue described here:
# https://github.com/kubernetes-client/python/pull/1863

from __future__ import annotations

from typing import Optional

from kubernetes.client import configuration, rest
from kubernetes.config import kube_config


class KubeConfigLoader(kube_config.KubeConfigLoader):
    def _load_cluster_info(self):
        super()._load_cluster_info()

        if "proxy-url" in self._cluster:
            self.proxy = self._cluster["proxy-url"]

        if "tls-server-name" in self._cluster:
            self.tls_server_name = self._cluster["tls-server-name"]

    def _set_config(self, client_configuration: Configuration):
        super()._set_config(client_configuration)

        for key in ["proxy", "tls_server_name"]:
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


# Patch RESTClientObject to pass server_hostname to urllib3
_original_rest_client_init = rest.RESTClientObject.__init__


def _patched_rest_client_init(self, configuration, pools_size=4, maxsize=None):
    # Call the original __init__ first
    _original_rest_client_init(self, configuration, pools_size, maxsize)

    # If tls_server_name is configured, we need to recreate the pool manager with server_hostname
    # We cannot simply modify connection_pool_kw after creation because connection pools
    # may already be instantiated. We must recreate the pool manager to ensure server_hostname
    # is passed to all new HTTPS connections for proper SNI (Server Name Indication) handling.
    if hasattr(configuration, "tls_server_name") and configuration.tls_server_name:
        # Import here to avoid overhead when tls_server_name is not used (common case)
        import ssl

        import certifi
        import urllib3
        from requests.utils import should_bypass_proxies

        # Reconstruct the same logic as the original __init__ but with server_hostname
        if configuration.verify_ssl:
            cert_reqs = ssl.CERT_REQUIRED
        else:
            cert_reqs = ssl.CERT_NONE

        if configuration.ssl_ca_cert:
            ca_certs = configuration.ssl_ca_cert
        else:
            ca_certs = certifi.where()

        addition_pool_args = {}
        if configuration.assert_hostname is not None:
            addition_pool_args["assert_hostname"] = configuration.assert_hostname

        if configuration.retries is not None:
            addition_pool_args["retries"] = configuration.retries

        if maxsize is None:
            if configuration.connection_pool_maxsize is not None:
                maxsize = configuration.connection_pool_maxsize
            else:
                maxsize = 4

        # Add server_hostname to connection kwargs
        addition_pool_args["server_hostname"] = configuration.tls_server_name

        # Recreate pool manager with server_hostname
        if configuration.proxy and not should_bypass_proxies(configuration.host, no_proxy=configuration.no_proxy or ""):
            self.pool_manager = urllib3.ProxyManager(
                num_pools=pools_size,
                maxsize=maxsize,
                cert_reqs=cert_reqs,
                ca_certs=ca_certs,
                cert_file=configuration.cert_file,
                key_file=configuration.key_file,
                proxy_url=configuration.proxy,
                proxy_headers=configuration.proxy_headers,
                **addition_pool_args,
            )
        else:
            self.pool_manager = urllib3.PoolManager(
                num_pools=pools_size,
                maxsize=maxsize,
                cert_reqs=cert_reqs,
                ca_certs=ca_certs,
                cert_file=configuration.cert_file,
                key_file=configuration.key_file,
                **addition_pool_args,
            )


rest.RESTClientObject.__init__ = _patched_rest_client_init
configuration.Configuration = Configuration
kube_config.KubeConfigLoader = KubeConfigLoader
