import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from robusta_krr.core.integrations.kubernetes import ClusterLoader
from robusta_krr.core.models.config import Config


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
    
    # Verify we got 2 objects (1 frontend + 1 backend, one per unique container name)
    assert len(result) == 2
    
    # Group results by name to verify grouping
    frontend_objects = [g for g in result if g.name == "app=frontend"]
    backend_objects = [g for g in result if g.name == "app=backend"]
    
    # Verify we got 1 frontend object (one per unique container name)
    assert len(frontend_objects) == 1
    assert frontend_objects[0].namespace == "default"
    assert frontend_objects[0].container == "main-container"
    
    # Verify we got 1 backend object (one per unique container name)  
    assert len(backend_objects) == 1
    assert backend_objects[0].namespace == "default"
    assert backend_objects[0].container == "main-container"
    
    # Verify all objects in each group have the same grouped_jobs list
    frontend_grouped_jobs = frontend_objects[0]._api_resource._grouped_jobs
    assert len(frontend_grouped_jobs) == 3
    assert frontend_grouped_jobs[0].metadata.name == "job-1"
    assert frontend_grouped_jobs[1].metadata.name == "job-2"
    assert frontend_grouped_jobs[2].metadata.name == "job-3"
    
    backend_grouped_jobs = backend_objects[0]._api_resource._grouped_jobs
    assert len(backend_grouped_jobs) == 3
    assert backend_grouped_jobs[0].metadata.name == "job-6"
    assert backend_grouped_jobs[1].metadata.name == "job-7"
    assert backend_grouped_jobs[2].metadata.name == "job-8"


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
    
    # Verify we got 2 objects (1 per namespace, one per unique container name)
    assert len(result) == 2
    
    # Group results by namespace
    ns1_objects = [g for g in result if g.namespace == "namespace-1"]
    ns2_objects = [g for g in result if g.namespace == "namespace-2"]
    
    # Check namespace-1 objects
    assert len(ns1_objects) == 1
    assert ns1_objects[0].name == "app=frontend"
    assert ns1_objects[0].container == "main-container"
    assert len(ns1_objects[0]._api_resource._grouped_jobs) == 2
    
    # Check namespace-2 objects
    assert len(ns2_objects) == 1
    assert ns2_objects[0].name == "app=frontend"
    assert ns2_objects[0].container == "main-container"
    assert len(ns2_objects[0]._api_resource._grouped_jobs) == 2


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
    
    # Verify we got 1 object (only the job without CronJob owner)
    assert len(result) == 1
    obj = result[0]
    assert obj.name == "app=frontend"
    assert len(obj._api_resource._grouped_jobs) == 1
    assert obj._api_resource._grouped_jobs[0].metadata.name == "job-1"


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
    
    # Verify we got 3 objects (one for each label+value combination, one per unique container name)
    assert len(result) == 3
    
    group_names = {g.name for g in result}
    assert "app=frontend" in group_names
    assert "team=backend" in group_names
    assert "app=api" in group_names
    
    # Verify all objects have the same container name
    assert all(obj.container == "main-container" for obj in result)
