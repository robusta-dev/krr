from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from prometrix import PrometheusConfig

from robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service import (
    ClientCertAdapter,
    PrometheusMetricsService,
)

MODULE = "robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service"
APISERVER = "https://10.0.0.1:6443"
PROXY_URL = f"{APISERVER}/api/v1/namespaces/monitoring/services/prometheus:9090/proxy"


def make_service(url, cert_file="/tmp/cert", key_file="/tmp/key", host=APISERVER, api_client=True):
    service = PrometheusMetricsService.__new__(PrometheusMetricsService)
    service.url = url
    service.api_client = (
        SimpleNamespace(configuration=SimpleNamespace(host=host, cert_file=cert_file, key_file=key_file))
        if api_client
        else None
    )
    return service


@pytest.fixture
def outside_cluster():
    with patch(f"{MODULE}.settings") as settings:
        settings.inside_cluster = False
        yield settings


def test_client_cert_sent_to_apiserver_proxy(outside_cluster):
    assert make_service(PROXY_URL)._get_apiserver_client_cert() == ("/tmp/cert", "/tmp/key")


@pytest.mark.parametrize(
    "url, host",
    [
        (PROXY_URL, APISERVER + "/"),
        ("HTTPS://10.0.0.1:6443/api/v1/namespaces/monitoring/services/prometheus:9090/proxy", APISERVER),
        (
            "https://API.example.com/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
            "https://api.example.com",
        ),
        (
            "https://api.example.com:443/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
            "https://api.example.com",
        ),
        (
            "https://api.example.com/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
            "https://api.example.com:443",
        ),
        (
            "https://rancher.example.com/k8s/clusters/c-1/api/v1/namespaces/m/services/p:9090/proxy",
            "https://rancher.example.com/k8s/clusters/c-1",
        ),
    ],
)
def test_client_cert_sent_to_equivalent_apiserver_urls(outside_cluster, url, host):
    assert make_service(url, host=host)._get_apiserver_client_cert() == ("/tmp/cert", "/tmp/key")


@pytest.mark.parametrize(
    "url",
    [
        "http://prometheus.example.com",
        "https://10.0.0.1:64430/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
        "https://10.0.0.1:6443.evil.example.com/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
        "http://10.0.0.1:6443/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
        "https://10.0.0.1:notaport/api/v1/namespaces/monitoring/services/prometheus:9090/proxy",
    ],
)
def test_client_cert_not_sent_to_other_hosts(outside_cluster, url):
    assert make_service(url)._get_apiserver_client_cert() is None


def test_client_cert_not_sent_outside_apiserver_path_prefix(outside_cluster):
    service = make_service(
        "https://rancher.example.com/k8s/clusters/c-10/api/v1/namespaces/m/services/p:9090/proxy",
        host="https://rancher.example.com/k8s/clusters/c-1",
    )
    assert service._get_apiserver_client_cert() is None


def test_no_client_cert_in_kubeconfig(outside_cluster):
    assert make_service(PROXY_URL, cert_file=None, key_file=None)._get_apiserver_client_cert() is None


def test_no_client_cert_without_api_client(outside_cluster):
    assert make_service(PROXY_URL, api_client=False)._get_apiserver_client_cert() is None


def test_no_client_cert_inside_cluster(outside_cluster):
    outside_cluster.inside_cluster = True
    assert make_service(PROXY_URL)._get_apiserver_client_cert() is None


def get_prometheus_session(client_cert):
    # Uses the real Prometheus client, so these tests fail if its requests session moves.
    service = make_service(PROXY_URL)
    service.headers = {}
    service.client_cert = client_cert
    service.prometheus = None
    service._last_init_at = None
    with patch(f"{MODULE}.generate_prometheus_config", return_value=PrometheusConfig(url=PROXY_URL)):
        return service.get_prometheus()._session


def test_client_cert_only_on_prometheus_url():
    session = get_prometheus_session(("/tmp/cert", "/tmp/key"))
    assert session.cert is None

    adapter = session.get_adapter(f"{PROXY_URL}/api/v1/query")
    assert isinstance(adapter, ClientCertAdapter)
    assert adapter.client_cert == ("/tmp/cert", "/tmp/key")
    assert adapter._pool_maxsize == 10
    assert adapter._pool_block is True

    # Where a redirect to another host would go.
    assert not isinstance(session.get_adapter("https://other.example.com/api/v1/query"), ClientCertAdapter)


def test_no_client_cert_adapter_without_cert():
    session = get_prometheus_session(None)
    assert not isinstance(session.get_adapter(f"{PROXY_URL}/api/v1/query"), ClientCertAdapter)


def test_client_cert_adapter_presents_cert():
    adapter = ClientCertAdapter(("/tmp/cert", "/tmp/key"))
    with patch("requests.adapters.HTTPAdapter.send", return_value="response") as send:
        assert adapter.send("request", cert=None, timeout=5) == "response"
    send.assert_called_once_with("request", cert=("/tmp/cert", "/tmp/key"), timeout=5)


def test_redirect_to_other_host_gets_no_client_cert():
    session = get_prometheus_session(("/tmp/cert", "/tmp/key"))
    sent = []

    def fake_send(adapter, request, **kwargs):
        sent.append((request.url, kwargs.get("cert")))
        response = requests.Response()
        response.request = request
        response.url = request.url
        if request.url.startswith(PROXY_URL):
            response.status_code = 302
            response.headers["Location"] = "https://other.example.com/api/v1/query"
        else:
            response.status_code = 200
        return response

    with patch("requests.adapters.HTTPAdapter.send", autospec=True, side_effect=fake_send):
        session.post(f"{PROXY_URL}/api/v1/query", data={"query": "up"})

    assert sent == [
        (f"{PROXY_URL}/api/v1/query", ("/tmp/cert", "/tmp/key")),
        ("https://other.example.com/api/v1/query", None),
    ]
