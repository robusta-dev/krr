import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collections import defaultdict

from robusta_krr.core.integrations.kubernetes import ClusterLoader
from robusta_krr.core.models.config import Config
from robusta_krr.api.models import K8sObjectData


@pytest.fixture
def mock_config():
    """Mock config with job grouping settings"""
    config = MagicMock(spec=Config)
    config.job_grouping_labels = ["app", "team"]
    config.job_grouping_limit = 3  # Small limit for testing
    config.max_workers = 4
    config.get_kube_client = MagicMock()
    config.resources = "*"
    return config


@pytest.fixture
def mock_kubernetes_loader(mock_config):
    """Create a ClusterLoader instance with mocked dependencies"""
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        loader = ClusterLoader()
        loader.batch = MagicMock()
        loader.core = MagicMock()
        loader.executor = MagicMock()
        loader._ClusterLoader__hpa_list = {} # type: ignore # needed for mock
        return loader


def create_mock_job(name: str, namespace: str, labels: dict):
    """Create a mock V1Job object"""
    job = MagicMock()
    job.metadata.name = name
    job.metadata.namespace = namespace
    job.metadata.labels = labels
    job.metadata.owner_references = []
    
    # Create a mock container with a proper name
    container = MagicMock()
    container.name = "main-container"
    job.spec.template.spec.containers = [container]
    return job


@pytest.mark.asyncio
async def test_list_all_groupedjobs_with_limit(mock_kubernetes_loader, mock_config):
    """Test that _list_all_groupedjobs respects the job_grouping_limit"""
    
    # Create mock jobs - more than the limit (3)
    mock_jobs = [
        create_mock_job("job-1", "default", {"app": "frontend"}),
        create_mock_job("job-2", "default", {"app": "frontend"}),
        create_mock_job("job-3", "default", {"app": "frontend"}),
        create_mock_job("job-4", "default", {"app": "frontend"}),  # This should be excluded
        create_mock_job("job-5", "default", {"app": "frontend"}),  # This should be excluded
        create_mock_job("job-6", "default", {"app": "backend"}),
        create_mock_job("job-7", "default", {"app": "backend"}),
        create_mock_job("job-8", "default", {"app": "backend"}),
        create_mock_job("job-9", "default", {"app": "backend"}),  # This should be excluded
    ]
    
    # Mock the _list_namespaced_or_global_objects method
    mock_kubernetes_loader._list_namespaced_or_global_objects = AsyncMock(return_value=mock_jobs)
    
    # Mock the __build_scannable_object method
    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        return obj
    
    mock_kubernetes_loader._KubernetesLoader__build_scannable_object = mock_build_scannable_object
    
    # Patch the settings to use our mock config
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        # Call the method
        result = await mock_kubernetes_loader._list_all_groupedjobs()
    
    # Verify we got 2 groups (frontend and backend)
    assert len(result) == 2
    
    # Find the frontend group
    frontend_group = next((g for g in result if g.name == "app=frontend"), None)
    assert frontend_group is not None
    assert frontend_group.namespace == "default"
    
    # Verify the frontend group is limited to 3 jobs (the limit)
    assert len(frontend_group._api_resource._grouped_jobs) == 3
    assert frontend_group._api_resource._grouped_jobs[0].metadata.name == "job-1"
    assert frontend_group._api_resource._grouped_jobs[1].metadata.name == "job-2"
    assert frontend_group._api_resource._grouped_jobs[2].metadata.name == "job-3"
    
    # Find the backend group
    backend_group = next((g for g in result if g.name == "app=backend"), None)
    assert backend_group is not None
    assert backend_group.namespace == "default"
    
    # Verify the backend group is also limited to 3 jobs
    assert len(backend_group._api_resource._grouped_jobs) == 3
    assert backend_group._api_resource._grouped_jobs[0].metadata.name == "job-6"
    assert backend_group._api_resource._grouped_jobs[1].metadata.name == "job-7"
    assert backend_group._api_resource._grouped_jobs[2].metadata.name == "job-8"


@pytest.mark.asyncio
async def test_list_all_groupedjobs_with_different_namespaces(mock_kubernetes_loader, mock_config):
    """Test that GroupedJob objects are created separately for different namespaces"""
    
    # Create mock jobs in different namespaces
    mock_jobs = [
        create_mock_job("job-1", "namespace-1", {"app": "frontend"}),
        create_mock_job("job-2", "namespace-1", {"app": "frontend"}),
        create_mock_job("job-3", "namespace-2", {"app": "frontend"}),
        create_mock_job("job-4", "namespace-2", {"app": "frontend"}),
    ]
    
    mock_kubernetes_loader._list_namespaced_or_global_objects = AsyncMock(return_value=mock_jobs)
    
    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        return obj
    
    mock_kubernetes_loader._KubernetesLoader__build_scannable_object = mock_build_scannable_object
    
    # Patch the settings to use our mock config
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        # Call the method
        result = await mock_kubernetes_loader._list_all_groupedjobs()
    
    # Verify we got 2 groups (one per namespace)
    assert len(result) == 2
    
    # Check namespace-1 group
    ns1_group = next((g for g in result if g.namespace == "namespace-1"), None)
    assert ns1_group is not None
    assert ns1_group.name == "app=frontend"
    assert len(ns1_group._api_resource._grouped_jobs) == 2
    
    # Check namespace-2 group
    ns2_group = next((g for g in result if g.namespace == "namespace-2"), None)
    assert ns2_group is not None
    assert ns2_group.name == "app=frontend"
    assert len(ns2_group._api_resource._grouped_jobs) == 2


@pytest.mark.asyncio
async def test_list_all_groupedjobs_with_cronjob_owner_reference(mock_kubernetes_loader, mock_config):
    """Test that jobs with CronJob owner references are excluded"""
    
    # Create mock jobs - one with CronJob owner, one without
    mock_jobs = [
        create_mock_job("job-1", "default", {"app": "frontend"}),
        create_mock_job("job-2", "default", {"app": "frontend"}),
    ]
    
    # Add CronJob owner reference to the second job
    mock_jobs[1].metadata.owner_references = [MagicMock(kind="CronJob")]
    
    mock_kubernetes_loader._list_namespaced_or_global_objects = AsyncMock(return_value=mock_jobs)
    
    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        return obj
    
    mock_kubernetes_loader._KubernetesLoader__build_scannable_object = mock_build_scannable_object
    
    # Patch the settings to use our mock config
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        # Call the method
        result = await mock_kubernetes_loader._list_all_groupedjobs()
    
    # Verify we got 1 group with only 1 job (the one without CronJob owner)
    assert len(result) == 1
    group = result[0]
    assert group.name == "app=frontend"
    assert len(group._api_resource._grouped_jobs) == 1
    assert group._api_resource._grouped_jobs[0].metadata.name == "job-1"


@pytest.mark.asyncio
async def test_list_all_groupedjobs_no_grouping_labels(mock_kubernetes_loader):
    """Test that no GroupedJob objects are created when no grouping labels are configured"""
    
    # Mock config with no grouping labels
    mock_config_no_labels = MagicMock(spec=Config)
    mock_config_no_labels.job_grouping_labels = None
    
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config_no_labels):
        result = await mock_kubernetes_loader._list_all_groupedjobs()
        assert len(result) == 0


@pytest.mark.asyncio
async def test_list_all_groupedjobs_multiple_labels(mock_kubernetes_loader, mock_config):
    """Test that jobs with different grouping labels create separate groups"""
    
    # Create mock jobs with different labels
    mock_jobs = [
        create_mock_job("job-1", "default", {"app": "frontend"}),
        create_mock_job("job-2", "default", {"team": "backend"}),
        create_mock_job("job-3", "default", {"app": "api"}),
    ]
    
    mock_kubernetes_loader._list_namespaced_or_global_objects = AsyncMock(return_value=mock_jobs)
    
    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        return obj
    
    mock_kubernetes_loader._KubernetesLoader__build_scannable_object = mock_build_scannable_object
    
    # Patch the settings to use our mock config
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        # Call the method
        result = await mock_kubernetes_loader._list_all_groupedjobs()
    
    # Verify we got 3 groups (one for each label+value combination)
    assert len(result) == 3
    
    group_names = {g.name for g in result}
    assert "app=frontend" in group_names
    assert "team=backend" in group_names
    assert "app=api" in group_names
