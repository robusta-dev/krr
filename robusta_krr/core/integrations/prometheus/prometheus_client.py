from typing import no_type_check

import requests
from datetime import datetime
from prometheus_api_client import PrometheusConnect, Retry, PrometheusApiClientException
from requests.adapters import HTTPAdapter


class ClusterNotSpecifiedException(Exception):
    """
    An exception raised when a prometheus requires a cluster label but an invalid one is provided.
    """

    pass


class CustomPrometheusConnect(PrometheusConnect):
    """
    Custom PrometheusConnect class to handle retries.
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:9090",
        headers: dict = None,
        disable_ssl: bool = False,
        retry: Retry = None,
        auth: tuple = None,
    ):
        super().__init__(url, headers, disable_ssl, retry, auth)
        self._session = requests.Session()
        self._session.mount(self.url, HTTPAdapter(max_retries=retry, pool_maxsize=10, pool_block=True))

    def custom_query(self, query: str, params: dict = None):
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

    def custom_query_range(
        self,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str,
        params: dict = None,
    ):
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
