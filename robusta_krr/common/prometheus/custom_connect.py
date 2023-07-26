from typing import Any, Dict, Optional

import requests
from botocore.auth import *
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from prometheus_api_client import PrometheusApiClientException, PrometheusConnect
from requests.adapters import HTTPAdapter
from requests.exceptions import ConnectionError, HTTPError

from ..prometheus.exceptions import PrometheusFlagsConnectionError, PrometheusNotFound, VictoriaMetricsNotFound
from ..prometheus.auth import PrometheusAuthorization
from ..prometheus.models import PrometheusApis, PrometheusConfig


class CustomPrometheusConnect(PrometheusConnect):
    def __init__(self, config: PrometheusConfig):
        super().__init__(url=config.url, disable_ssl=config.disable_ssl, headers=config.headers)
        self.config = config
        self._session = requests.Session()
        self._session.mount(self.url, HTTPAdapter(pool_maxsize=10, pool_block=True))

    def custom_query_range(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str,
        params: dict = None,
    ):
        """
        The main difference here is that the method here is POST and the prometheus_cli is GET
        """
        start = round(start_time.timestamp())
        end = round(end_time.timestamp())
        params = params or {}
        data = None
        query = str(query)
        # using the query_range API to get raw data
        response = self._session.post(
            "{0}/api/v1/query_range".format(self.url),
            data={
                "query": query,
                "start": start,
                "end": end,
                "step": step,
                **params,
            },
            verify=self.ssl_verification,
            headers=self.headers,
            auth=self.auth,
        )
        if response.status_code == 200:
            data = response.json()["data"]["result"]
        else:
            raise PrometheusApiClientException(
                "HTTP Status Code {} ({!r})".format(response.status_code, response.content)
            )
        return data

    def custom_query(self, query: str, params: dict = None):
        """
        The main difference here is that the method here is POST and the prometheus_cli is GET
        """
        params = params or {}
        data = None
        query = str(query)
        # using the query API to get raw data
        response = self._session.post(
            "{0}/api/v1/query".format(self.url),
            data={"query": query, **params},
            verify=self.ssl_verification,
            headers=self.headers,
            auth=self.auth,
        )
        if response.status_code == 200:
            data = response.json()["data"]["result"]
        else:
            raise PrometheusApiClientException(
                "HTTP Status Code {} ({!r})".format(response.status_code, response.content)
            )

        return data

    def check_prometheus_connection(self, params: dict = None):
        params = params or {}
        try:
            if isinstance(self, AWSPrometheusConnect):
                # will throw exception if not 200
                return self.custom_query(query="example")
            else:
                response = self._session.get(
                    f"{self.url}/api/v1/query",
                    verify=self.ssl_verification,
                    headers=self.headers,
                    # This query should return empty results, but is correct
                    params={"query": "example", **params},
                    context={},
                )
            if response.status_code == 401:
                if PrometheusAuthorization.request_new_token(self.config):
                    self.headers = PrometheusAuthorization.get_authorization_headers(self.config)
                    response = self._session.get(
                        f"{self.url}/api/v1/query",
                        verify=self.ssl_verification,
                        headers=self.headers,
                        params={"query": "example", **params},
                    )

            response.raise_for_status()
        except (ConnectionError, HTTPError, PrometheusApiClientException) as e:
            raise PrometheusNotFound(
                f"Couldn't connect to Prometheus found under {self.url}\nCaused by {e.__class__.__name__}: {e})"
            ) from e

    def __text_config_to_dict(self, text: str) -> Dict:
        conf = {}
        lines = text.strip().split("\n")
        for line in lines:
            key, val = line.strip().split("=")
            conf[key] = val.strip('"')

        return conf

    def get_prometheus_flags(self) -> Optional[Dict]:
        try:
            if PrometheusApis.FLAGS in self.config.supported_apis:
                return self.fetch_prometheus_flags()
            if PrometheusApis.VM_FLAGS in self.config.supported_apis:
                return self.fetch_victoria_metrics_flags()
        except Exception as e:
            service_name = "Prometheus" if PrometheusApis.FLAGS in self.config.supported_apis else "Victoria Metrics"
            raise PrometheusFlagsConnectionError(f"Couldn't connect to the url: {self.url}\n\t\t{service_name}: {e}")

    def fetch_prometheus_flags(self) -> Dict:
        try:
            response = self._session.get(
                f"{self.url}/api/v1/status/flags",
                verify=self.ssl_verification,
                headers=self.headers,
                # This query should return empty results, but is correct
                params={},
            )
            response.raise_for_status()
            return response.json().get("data", {})
        except Exception as e:
            raise PrometheusNotFound(
                f"Couldn't connect to Prometheus found under {self.url}\nCaused by {e.__class__.__name__}: {e})"
            ) from e

    def fetch_victoria_metrics_flags(self) -> Dict:
        try:
            # connecting to VictoriaMetrics
            response = self._session.get(
                f"{self.url}/flags",
                verify=self.ssl_verification,
                headers=self.headers,
                # This query should return empty results, but is correct
                params={},
            )
            response.raise_for_status()

            configuration = self.__text_config_to_dict(response.text)
            return configuration
        except Exception as e:
            raise VictoriaMetricsNotFound(
                f"Couldn't connect to VictoriaMetrics found under {self.url}\nCaused by {e.__class__.__name__}: {e})"
            ) from e


class AWSPrometheusConnect(CustomPrometheusConnect):
    def __init__(self, access_key: str, secret_key: str, region: str, service_name: str, **kwargs):
        super().__init__(**kwargs)
        self._credentials = Credentials(access_key, secret_key)
        self._sigv4auth = S3SigV4Auth(self._credentials, service_name, region)

    def signed_request(self, method, url, data=None, params=None, verify=False, headers=None):
        request = AWSRequest(method=method, url=url, data=data, params=params, headers=headers)
        self._sigv4auth.add_auth(request)
        return requests.request(method=method, url=url, headers=dict(request.headers), verify=verify, data=data)

    def custom_query(self, query: str, params: dict = None):
        """
        Send a custom query to a Prometheus Host.

        This method takes as input a string which will be sent as a query to
        the specified Prometheus Host. This query is a PromQL query.

        :param query: (str) This is a PromQL query, a few examples can be found
            at https://prometheus.io/docs/prometheus/latest/querying/examples/
        :param params: (dict) Optional dictionary containing GET parameters to be
            sent along with the API request, such as "time"
        :returns: (list) A list of metric data received in response of the query sent
        :raises:
            (RequestException) Raises an exception in case of a connection error
            (PrometheusApiClientException) Raises in case of non 200 response status code
        """
        params = params or {}
        data = None
        query = str(query)
        # using the query API to get raw data
        response = self.signed_request(
            method="POST",
            url="{0}/api/v1/query".format(self.url),
            data={**{"query": query}, **params},
            params={},
            verify=self.ssl_verification,
            headers=self.headers,
        )
        if response.status_code == 200:
            data = response.json()["data"]["result"]
        else:
            raise PrometheusApiClientException(
                "HTTP Status Code {} ({!r})".format(response.status_code, response.content)
            )

        return data

    def custom_query_range(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str,
        params: Optional[Dict[str, Any]] = None,
    ):
        """
        Send a query_range to a Prometheus Host.
        This method takes as input a string which will be sent as a query to
        the specified Prometheus Host. This query is a PromQL query.
        :param query: (str) This is a PromQL query, a few examples can be found
            at https://prometheus.io/docs/prometheus/latest/querying/examples/
        :param start_time: (datetime) A datetime object that specifies the query range start time.
        :param end_time: (datetime) A datetime object that specifies the query range end time.
        :param step: (str) Query resolution step width in duration format or float number of seconds - i.e 100s, 3d, 2w, 170.3
        :param params: (dict) Optional dictionary containing GET parameters to be
            sent along with the API request, such as "timeout"
        :returns: (dict) A dict of metric data received in response of the query sent
        :raises:
            (RequestException) Raises an exception in case of a connection error
            (PrometheusApiClientException) Raises in case of non 200 response status code
        """
        start = round(start_time.timestamp())
        end = round(end_time.timestamp())
        params = params or {}

        prometheus_result = None
        query = str(query)
        response = self.signed_request(
            method="POST",
            url="{0}/api/v1/query_range".format(self.url),
            data={**{"query": query, "start": start, "end": end, "step": step}, **params},
            params={},
            headers=self.headers,
        )
        if response.status_code == 200:
            prometheus_result = data=response.json()["data"]["result"]
        else:
            raise PrometheusApiClientException(
                "HTTP Status Code {} ({!r})".format(response.status_code, response.content)
            )
        return prometheus_result

    def check_prometheus_connection(self, params: dict = None) -> bool:
        """
        Check Promethus connection.

        :param params: (dict) Optional dictionary containing parameters to be
            sent along with the API request.
        :returns: (bool) True if the endpoint can be reached, False if cannot be reached.
        """
        return self.custom_query(query="example", params=params)
