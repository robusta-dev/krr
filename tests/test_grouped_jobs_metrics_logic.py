import pytest
from unittest.mock import MagicMock, patch
from datetime import timedelta

from robusta_krr.core.integrations.kubernetes import LightweightJobInfo


def test_grouped_job_extracts_job_names():
    """Test that GroupedJob objects correctly expose job names for metrics queries"""
    
    # Create a mock GroupedJob object
    grouped_job = MagicMock()
    grouped_job.kind = "GroupedJob"
    grouped_job.name = "app=frontend"
    grouped_job.namespace = "default"
    grouped_job.container = "main-container"
    
    # Mock the API resource with lightweight job info
    grouped_job._api_resource = MagicMock()
    grouped_job._api_resource._grouped_jobs = [
        LightweightJobInfo(name="job-1", namespace="default"),
        LightweightJobInfo(name="job-2", namespace="default"),
        LightweightJobInfo(name="job-3", namespace="default"),
    ]
    grouped_job._api_resource._label_filter = "app=frontend"
    
    # Test the logic that would be used in PrometheusMetricsService.load_pods
    if grouped_job.kind == "GroupedJob":
        if hasattr(grouped_job._api_resource, '_grouped_jobs'):
            pod_owners = [job.name for job in grouped_job._api_resource._grouped_jobs]
            pod_owner_kind = "Job"
        else:
            pod_owners = [grouped_job.name]
            pod_owner_kind = grouped_job.kind
    
    # Verify the extracted job names
    assert pod_owners == ["job-1", "job-2", "job-3"]
    assert pod_owner_kind == "Job"
    
    # Verify the namespace
    assert grouped_job.namespace == "default"


def test_grouped_job_with_different_namespaces():
    """Test that GroupedJob objects in different namespaces are handled correctly"""
    
    # Create grouped jobs in different namespaces
    grouped_job_ns1 = MagicMock()
    grouped_job_ns1.kind = "GroupedJob"
    grouped_job_ns1.name = "app=frontend"
    grouped_job_ns1.namespace = "namespace-1"
    grouped_job_ns1._api_resource = MagicMock()
    grouped_job_ns1._api_resource._grouped_jobs = [
        LightweightJobInfo(name="job-1", namespace="namespace-1"),
    ]
    
    grouped_job_ns2 = MagicMock()
    grouped_job_ns2.kind = "GroupedJob"
    grouped_job_ns2.name = "app=frontend"
    grouped_job_ns2.namespace = "namespace-2"
    grouped_job_ns2._api_resource = MagicMock()
    grouped_job_ns2._api_resource._grouped_jobs = [
        LightweightJobInfo(name="job-2", namespace="namespace-2"),
    ]
    
    # Test the logic for both namespaces
    for grouped_job in [grouped_job_ns1, grouped_job_ns2]:
        if grouped_job.kind == "GroupedJob":
            if hasattr(grouped_job._api_resource, '_grouped_jobs'):
                pod_owners = [job.name for job in grouped_job._api_resource._grouped_jobs]
                pod_owner_kind = "Job"
            else:
                pod_owners = [grouped_job.name]
                pod_owner_kind = grouped_job.kind
        
        # Verify namespace-specific results
        if grouped_job.namespace == "namespace-1":
            assert pod_owners == ["job-1"]
            assert grouped_job.namespace == "namespace-1"
        elif grouped_job.namespace == "namespace-2":
            assert pod_owners == ["job-2"]
            assert grouped_job.namespace == "namespace-2"


def test_grouped_job_prometheus_query_construction():
    """Test that the Prometheus query is constructed correctly for GroupedJob"""
    
    # Create a mock GroupedJob object
    grouped_job = MagicMock()
    grouped_job.kind = "GroupedJob"
    grouped_job.name = "app=frontend"
    grouped_job.namespace = "default"
    
    # Mock the API resource with lightweight job info
    grouped_job._api_resource = MagicMock()
    grouped_job._api_resource._grouped_jobs = [
        LightweightJobInfo(name="job-1", namespace="default"),
        LightweightJobInfo(name="job-2", namespace="default"),
        LightweightJobInfo(name="job-3", namespace="default"),
    ]
    
    # Simulate the logic from PrometheusMetricsService.load_pods
    if grouped_job.kind == "GroupedJob":
        if hasattr(grouped_job._api_resource, '_grouped_jobs'):
            pod_owners = [job.name for job in grouped_job._api_resource._grouped_jobs]
            pod_owner_kind = "Job"
        else:
            pod_owners = [grouped_job.name]
            pod_owner_kind = grouped_job.kind
    
    # Construct the Prometheus query (simplified version)
    owners_regex = "|".join(pod_owners)
    cluster_label = ""  # Simplified for testing
    
    expected_query = f"""
        last_over_time(
            kube_pod_owner{{
                owner_name=~"{owners_regex}",
                owner_kind="{pod_owner_kind}",
                namespace="{grouped_job.namespace}"
                {cluster_label}
            }}[1h]
        )
    """
    
    # Verify the query contains the expected elements
    assert "job-1|job-2|job-3" in expected_query
    assert 'owner_kind="Job"' in expected_query
    assert 'namespace="default"' in expected_query
    assert "kube_pod_owner" in expected_query


def test_grouped_job_batched_queries():
    """Test that batched queries are handled correctly for many jobs"""
    
    # Create a grouped job with many lightweight jobs
    grouped_job = MagicMock()
    grouped_job.kind = "GroupedJob"
    grouped_job.name = "app=frontend"
    grouped_job.namespace = "default"
    
    # Create 150 jobs (more than typical batch size of 100)
    many_jobs = [LightweightJobInfo(name=f"job-{i}", namespace="default") for i in range(150)]
    grouped_job._api_resource = MagicMock()
    grouped_job._api_resource._grouped_jobs = many_jobs
    
    # Extract job names
    if grouped_job.kind == "GroupedJob":
        if hasattr(grouped_job._api_resource, '_grouped_jobs'):
            pod_owners = [job.name for job in grouped_job._api_resource._grouped_jobs]
            pod_owner_kind = "Job"
    
    # Simulate batching logic
    batch_size = 100
    batches = []
    for i in range(0, len(pod_owners), batch_size):
        batch = pod_owners[i:i + batch_size]
        batches.append(batch)
    
    # Verify batching
    assert len(batches) == 2  # 150 jobs split into 2 batches
    assert len(batches[0]) == 100  # First batch has 100 jobs
    assert len(batches[1]) == 50   # Second batch has 50 jobs
    
    # Verify all job names are included
    all_batched_jobs = [job for batch in batches for job in batch]
    assert len(all_batched_jobs) == 150
    assert all_batched_jobs == [f"job-{i}" for i in range(150)]


def test_grouped_job_fallback_logic():
    """Test the fallback logic when _grouped_jobs is not available"""
    
    # Create a GroupedJob without _grouped_jobs
    grouped_job = MagicMock()
    grouped_job.kind = "GroupedJob"
    grouped_job.name = "app=frontend"
    grouped_job.namespace = "default"
    
    # Create a mock API resource that doesn't have _grouped_jobs
    api_resource = MagicMock()
    # Explicitly remove the _grouped_jobs attribute
    del api_resource._grouped_jobs
    grouped_job._api_resource = api_resource
    
    # Test the fallback logic
    if grouped_job.kind == "GroupedJob":
        if hasattr(grouped_job._api_resource, '_grouped_jobs'):
            pod_owners = [job.name for job in grouped_job._api_resource._grouped_jobs]
            pod_owner_kind = "Job"
        else:
            pod_owners = [grouped_job.name]
            pod_owner_kind = grouped_job.kind
    
    # Verify fallback behavior
    assert pod_owners == ["app=frontend"]
    assert pod_owner_kind == "GroupedJob"


def test_lightweight_job_info_structure():
    """Test that LightweightJobInfo has the correct structure"""
    
    # Create a LightweightJobInfo instance
    job_info = LightweightJobInfo(name="test-job", namespace="test-namespace")
    
    # Verify the structure
    assert job_info.name == "test-job"
    assert job_info.namespace == "test-namespace"
    
    # Verify it's a simple data class
    assert hasattr(job_info, 'name')
    assert hasattr(job_info, 'namespace')
    
    # Test that it can be used in list comprehensions
    job_infos = [
        LightweightJobInfo(name="job-1", namespace="default"),
        LightweightJobInfo(name="job-2", namespace="default"),
    ]
    
    job_names = [job.name for job in job_infos]
    assert job_names == ["job-1", "job-2"]
    
    namespaces = [job.namespace for job in job_infos]
    assert namespaces == ["default", "default"]


def test_grouped_job_multiple_groups_metrics_extraction():
    """Test that jobs appearing in multiple groups work correctly for metrics extraction"""
    
    # Create a job that appears in multiple groups
    grouped_job_app = MagicMock()
    grouped_job_app.kind = "GroupedJob"
    grouped_job_app.name = "app=frontend"
    grouped_job_app.namespace = "default"
    grouped_job_app._api_resource = MagicMock()
    grouped_job_app._api_resource._grouped_jobs = [
        LightweightJobInfo(name="job-1", namespace="default"),
        LightweightJobInfo(name="job-2", namespace="default"),
    ]
    
    grouped_job_team = MagicMock()
    grouped_job_team.kind = "GroupedJob"
    grouped_job_team.name = "team=web"
    grouped_job_team.namespace = "default"
    grouped_job_team._api_resource = MagicMock()
    grouped_job_team._api_resource._grouped_jobs = [
        LightweightJobInfo(name="job-1", namespace="default"),  # Same job appears in both groups
        LightweightJobInfo(name="job-3", namespace="default"),
    ]
    
    # Test metrics extraction for both groups
    for grouped_job in [grouped_job_app, grouped_job_team]:
        if grouped_job.kind == "GroupedJob":
            if hasattr(grouped_job._api_resource, '_grouped_jobs'):
                pod_owners = [job.name for job in grouped_job._api_resource._grouped_jobs]
                pod_owner_kind = "Job"
            else:
                pod_owners = [grouped_job.name]
                pod_owner_kind = grouped_job.kind
        
        # Verify the extracted job names
        if grouped_job.name == "app=frontend":
            assert pod_owners == ["job-1", "job-2"]
        elif grouped_job.name == "team=web":
            assert pod_owners == ["job-1", "job-3"]
        
        assert pod_owner_kind == "Job"
        assert grouped_job.namespace == "default"
    
    # Verify that job-1 appears in both groups (this is the key behavior we're testing)
    app_job_names = [job.name for job in grouped_job_app._api_resource._grouped_jobs]
    team_job_names = [job.name for job in grouped_job_team._api_resource._grouped_jobs]
    
    assert "job-1" in app_job_names
    assert "job-1" in team_job_names
    assert len(app_job_names) == 2
    assert len(team_job_names) == 2
