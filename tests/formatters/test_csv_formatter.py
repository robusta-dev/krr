import csv
import io
import json
from typing import Any

import pytest

from robusta_krr.core.models.config import Config
from robusta_krr.core.models.result import Result
from robusta_krr.formatters.csv import csv_exporter

RESULT = """
{
    "scans": [
        {
            "object": {
                "cluster": "mock-cluster",
                "name": "mock-object-1",
                "container": "mock-container-1",
                "pods": [
                    {
                        "name": "mock-pod-1",
                        "deleted": false
                    },
                    {
                        "name": "mock-pod-2",
                        "deleted": false
                    },
                    {
                        "name": "mock-pod-3",
                        "deleted": true
                    }
                ],
                "hpa": null,
                "namespace": "default",
                "kind": "Deployment",
                "allocations": {
                    "requests": {
                        "cpu": "50m",
                        "memory": "2048Mi"
                    },
                    "limits": {
                        "cpu": 2.0,
                        "memory": 2.0
                    },
                    "info": {}
                },
                "warnings": []
            },
            "recommended": {
                "requests": {
                    "cpu": {
                        "value": 0.0065,
                        "severity": "UNKNOWN"
                    },
                    "memory": {
                        "value": 0.5,
                        "severity": "CRITICAL"
                    }
                },
                "limits": {
                    "cpu": {
                        "value": "?",
                        "severity": "UNKNOWN"
                    },
                    "memory": {
                        "value": 0.5,
                        "severity": "CRITICAL"
                    }
                },
                "info": {
                    "cpu": "Not enough data",
                    "memory": "Not enough data"
                }
            },
            "severity": "CRITICAL"
        }
    ],
    "score": 100,
    "resources": [
        "cpu",
        "memory"
    ],
    "description": "tests data",
    "strategy": {
        "name": "simple",
        "settings": {
            "history_duration": 336.0,
            "timeframe_duration": 1.25,
            "cpu_percentile": 95.0,
            "memory_buffer_percentage": 15.0,
            "points_required": 100,
            "allow_hpa": false,
            "use_oomkill_data": false,
            "oom_memory_buffer_percentage": 25.0
        }
    },
    "errors": [],
    "clusterSummary": {},
    "config": {
        "quiet": false,
        "verbose": false,
        "clusters": [],
        "kubeconfig": null,
        "impersonate_user": null,
        "impersonate_group": null,
        "namespaces": "*",
        "resources": [],
        "selector": null,
        "cpu_min_value": 10,
        "memory_min_value": 100,
        "cpu_min_diff": 0,
        "memory_min_diff": 0,
        "cpu_min_percent": 0,
        "memory_min_percent": 0,
        "prometheus_url": null,
        "prometheus_auth_header": null,
        "prometheus_other_headers": {},
        "prometheus_ssl_enabled": false,
        "prometheus_cluster_label": null,
        "prometheus_label": null,
        "eks_managed_prom": false,
        "eks_managed_prom_profile_name": null,
        "eks_access_key": null,
        "eks_secret_key": null,
        "eks_service_name": "aps",
        "eks_managed_prom_region": null,
        "coralogix_token": null,
        "openshift": false,
        "max_workers": 10,
        "format": "csv",
        "show_cluster_name": false,
        "strategy": "simple",
        "log_to_stderr": false,
        "width": null,
        "file_output": null,
        "slack_output": null,
        "other_args": {
            "history_duration": "336",
            "timeframe_duration": "1.25",
            "cpu_percentile": "95",
            "memory_buffer_percentage": "15",
            "points_required": "100",
            "allow_hpa": false,
            "use_oomkill_data": false,
            "oom_memory_buffer_percentage": "25"
        },
        "inside_cluster": false,
        "file_output_dynamic": false
    }
}
"""


def _load_result(override_config: dict[str, Any]) -> Result:
    res_data = json.loads(RESULT)
    res_data["config"].update(override_config)
    result = Result(**res_data)
    Config.set_config(result.config)
    return result


@pytest.mark.parametrize(
    "override_config, expected_headers",
    [
        (
            {},
            [
                "Namespace",
                "Name",
                "Pods",
                "Old Pods",
                "Type",
                "Container",
                "Severity",
                "CPU Diff",
                "CPU Requests",
                "CPU Limits",
                "Memory Diff",
                "Memory Requests",
                "Memory Limits",
            ],
        ),
        (
            {"show_severity": False},
            [
                "Namespace",
                "Name",
                "Pods",
                "Old Pods",
                "Type",
                "Container",
                "CPU Diff",
                "CPU Requests",
                "CPU Limits",
                "Memory Diff",
                "Memory Requests",
                "Memory Limits",
            ],
        ),
        (
            {"show_cluster_name": True},
            [
                "Cluster",
                "Namespace",
                "Name",
                "Pods",
                "Old Pods",
                "Type",
                "Container",
                "Severity",
                "CPU Diff",
                "CPU Requests",
                "CPU Limits",
                "Memory Diff",
                "Memory Requests",
                "Memory Limits",
            ],
        ),
    ],
)
def test_csv_headers(override_config: dict[str, Any], expected_headers: list[str]) -> None:
    result = _load_result(override_config=override_config)
    output = csv_exporter(result)
    reader = csv.DictReader(io.StringIO(output))

    assert reader.fieldnames == expected_headers


@pytest.mark.parametrize(
    "override_config, expected_first_row",
    [
        (
            {},
            {
                "Namespace": "default",
                "Name": "mock-object-1",
                "Pods": "2",
                "Old Pods": "1",
                "Type": "Deployment",
                "Container": "mock-container-1",
                'Severity': 'CRITICAL',
                "CPU Diff": "-87m",
                "CPU Requests": "(-43m) 50m -> 6m",
                "CPU Limits": "2.0 -> ?",
                "Memory Diff": "-4096Mi",
                "Memory Requests": "(-2048Mi) 2048Mi -> 500m",
                "Memory Limits": "2.0 -> 500m",
            },
        ),
        (
            {"show_severity": False},
            {
                "Namespace": "default",
                "Name": "mock-object-1",
                "Pods": "2",
                "Old Pods": "1",
                "Type": "Deployment",
                "Container": "mock-container-1",
                "CPU Diff": "-87m",
                "CPU Requests": "(-43m) 50m -> 6m",
                "CPU Limits": "2.0 -> ?",
                "Memory Diff": "-4096Mi",
                "Memory Requests": "(-2048Mi) 2048Mi -> 500m",
                "Memory Limits": "2.0 -> 500m",
            },
        ),
        (
            {"show_cluster_name": True},
            {
                "Cluster": "mock-cluster",
                "Namespace": "default",
                "Name": "mock-object-1",
                "Pods": "2",
                "Old Pods": "1",
                "Type": "Deployment",
                "Container": "mock-container-1",
                'Severity': 'CRITICAL',
                "CPU Diff": "-87m",
                "CPU Requests": "(-43m) 50m -> 6m",
                "CPU Limits": "2.0 -> ?",
                "Memory Diff": "-4096Mi",
                "Memory Requests": "(-2048Mi) 2048Mi -> 500m",
                "Memory Limits": "2.0 -> 500m",
            },
        ),
    ],
)
def test_csv_row_value(override_config: dict[str, Any], expected_first_row: list[str]) -> None:
    result = _load_result(override_config=override_config)
    output = csv_exporter(result)
    reader = csv.DictReader(io.StringIO(output))

    first_row: dict[str, Any] = next(reader)
    assert first_row == expected_first_row
