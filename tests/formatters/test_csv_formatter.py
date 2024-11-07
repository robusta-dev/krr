import json
from typing import Any
from robusta_krr.core.models.result import Result
from robusta_krr.formatters.csv import csv_exporter
import io
import csv

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
                        "cpu": 1.0,
                        "memory": 1.0
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
                        "value": "?",
                        "severity": "UNKNOWN"
                    },
                    "memory": {
                        "value": "?",
                        "severity": "UNKNOWN"
                    }
                },
                "limits": {
                    "cpu": {
                        "value": "?",
                        "severity": "UNKNOWN"
                    },
                    "memory": {
                        "value": "?",
                        "severity": "UNKNOWN"
                    }
                },
                "info": {
                    "cpu": "Not enough data",
                    "memory": "Not enough data"
                }
            },
            "severity": "UNKNOWN"
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
        "file_output_dynamic": false,
        "bool": false
    }
}
"""


def test_csv_headers() -> None:
    res_data = json.loads(RESULT)
    result = Result(**res_data)
    x = csv_exporter(result)
    reader = csv.DictReader(io.StringIO(x))

    expected_headers: list[str] = [
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
    ]
    assert reader.fieldnames == expected_headers

    expected_first_row: dict[str, str] = {
        "Namespace": "default",
        "Name": "mock-object-1",
        "Pods": "2",
        "Old Pods": "1",
        "Type": "Deployment",
        "Container": "mock-container-1",
        "CPU Diff": "",
        "CPU Requests": "1.0 -> ?",
        "CPU Limits": "2.0 -> ?",
        "Memory Diff": "",
        "Memory Requests": "1.0 -> ?",
        "Memory Limits": "2.0 -> ?",
    }
    first_row: dict[str, Any] = next(reader)
    assert first_row == expected_first_row
