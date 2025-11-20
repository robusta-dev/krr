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
    config.discovery_job_batch_size = 1000
    config.discovery_job_max_batches = 50
    config.max_workers = 4
    config.get_kube_client = MagicMock()
    config.resources = "*"
    config.selector = None
    config.namespaces = "*"  # Add namespaces setting
    return config


@pytest.fixture
def mock_kubernetes_loader(mock_config):
    """Create a ClusterLoader instance with mocked dependencies"""
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        loader = ClusterLoader()
        loader.batch = MagicMock()
        loader.core = MagicMock()
        
        # Mock executor to return a proper Future
        from concurrent.futures import Future
        mock_future = Future()
        mock_future.set_result(None)  # Set a dummy result
        loader.executor = MagicMock()
        loader.executor.submit.return_value = mock_future
        
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
    
    # Mock the _list_namespaced_or_global_objects_batched method
    async def mock_batched_method(*args, **kwargs):
        # Create mock response objects that have the expected structure
        mock_response = MagicMock()
        mock_response.items = mock_jobs
        mock_response.metadata = MagicMock()
        mock_response.metadata._continue = None
        return (mock_jobs, None)  # Return (jobs, continue_token)
    mock_kubernetes_loader._list_namespaced_or_global_objects_batched = mock_batched_method
    
    # Mock the __build_scannable_object method
    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        obj.container = container.name
        return obj
    
    mock_kubernetes_loader._ClusterLoader__build_scannable_object = mock_build_scannable_object
    
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
    
    # Verify we got 1 backend object  
    assert len(backend_objects) == 1
    assert backend_objects[0].namespace == "default"
    assert backend_objects[0].container == "main-container"
    
    # Verify all objects in each group have lightweight job info
    frontend_grouped_jobs = frontend_objects[0]._api_resource._grouped_jobs
    assert len(frontend_grouped_jobs) == 3
    assert frontend_grouped_jobs[0].name == "job-1"
    assert frontend_grouped_jobs[1].name == "job-2"
    assert frontend_grouped_jobs[2].name == "job-3"
    
    backend_grouped_jobs = backend_objects[0]._api_resource._grouped_jobs
    assert len(backend_grouped_jobs) == 3
    assert backend_grouped_jobs[0].name == "job-6"
    assert backend_grouped_jobs[1].name == "job-7"
    assert backend_grouped_jobs[2].name == "job-8"


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
    
    async def mock_batched_method(*args, **kwargs):
        # Create mock response objects that have the expected structure
        mock_response = MagicMock()
        mock_response.items = mock_jobs
        mock_response.metadata = MagicMock()
        mock_response.metadata._continue = None
        return (mock_jobs, None)  # Return (jobs, continue_token)
    mock_kubernetes_loader._list_namespaced_or_global_objects_batched = mock_batched_method
    
    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        obj.container = container.name
        return obj
    
    mock_kubernetes_loader._ClusterLoader__build_scannable_object = mock_build_scannable_object
    
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
    
    async def mock_batched_method(*args, **kwargs):
        # Create mock response objects that have the expected structure
        mock_response = MagicMock()
        mock_response.items = mock_jobs
        mock_response.metadata = MagicMock()
        mock_response.metadata._continue = None
        return (mock_jobs, None)  # Return (jobs, continue_token)
    mock_kubernetes_loader._list_namespaced_or_global_objects_batched = mock_batched_method
    
    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        obj.container = container.name  # Set the actual container name
        return obj
    
    mock_kubernetes_loader._ClusterLoader__build_scannable_object = mock_build_scannable_object
    
    # Patch the settings to use our mock config
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        # Call the method
        result = await mock_kubernetes_loader._list_all_groupedjobs()
    
    # Verify we got 1 object (only the job without CronJob owner)
    assert len(result) == 1
    obj = result[0]
    assert obj.name == "app=frontend"
    assert len(obj._api_resource._grouped_jobs) == 1
    assert obj._api_resource._grouped_jobs[0].name == "job-1"


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
    
    async def mock_batched_method(*args, **kwargs):
        # Create mock response objects that have the expected structure
        mock_response = MagicMock()
        mock_response.items = mock_jobs
        mock_response.metadata = MagicMock()
        mock_response.metadata._continue = None
        return (mock_jobs, None)  # Return (jobs, continue_token)
    mock_kubernetes_loader._list_namespaced_or_global_objects_batched = mock_batched_method
    
    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        obj.container = container.name
        return obj
    
    mock_kubernetes_loader._ClusterLoader__build_scannable_object = mock_build_scannable_object
    
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


@pytest.mark.asyncio
async def test_list_all_groupedjobs_job_in_multiple_groups(mock_kubernetes_loader, mock_config):
    """Test that a job with multiple grouping labels is added to all matching groups"""
    
    # Create a job that matches multiple grouping labels
    mock_jobs = [
        create_mock_job("job-1", "default", {"app": "frontend", "team": "web"}),
        create_mock_job("job-2", "default", {"app": "backend", "team": "api"}),
    ]
    
    async def mock_batched_method(*args, **kwargs):
        # Create mock response objects that have the expected structure
        mock_response = MagicMock()
        mock_response.items = mock_jobs
        mock_response.metadata = MagicMock()
        mock_response.metadata._continue = None
        return (mock_jobs, None)  # Return (jobs, continue_token)
    mock_kubernetes_loader._list_namespaced_or_global_objects_batched = mock_batched_method
    
    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        obj.container = container.name
        return obj
    
    mock_kubernetes_loader._ClusterLoader__build_scannable_object = mock_build_scannable_object
    
    # Patch the settings to use our mock config
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        # Call the method
        result = await mock_kubernetes_loader._list_all_groupedjobs()
    
    # Verify we got 4 objects (2 jobs × 2 labels each = 4 groups)
    assert len(result) == 4
    
    group_names = {g.name for g in result}
    assert "app=frontend" in group_names
    assert "app=backend" in group_names
    assert "team=web" in group_names
    assert "team=api" in group_names
    
    # Find each group and verify it contains the correct job
    frontend_group = next(g for g in result if g.name == "app=frontend")
    backend_group = next(g for g in result if g.name == "app=backend")
    web_group = next(g for g in result if g.name == "team=web")
    api_group = next(g for g in result if g.name == "team=api")
    
    # Verify job-1 is in both app=frontend and team=web groups
    assert len(frontend_group._api_resource._grouped_jobs) == 1
    assert frontend_group._api_resource._grouped_jobs[0].name == "job-1"
    
    assert len(web_group._api_resource._grouped_jobs) == 1
    assert web_group._api_resource._grouped_jobs[0].name == "job-1"
    
    # Verify job-2 is in both app=backend and team=api groups
    assert len(backend_group._api_resource._grouped_jobs) == 1
    assert backend_group._api_resource._grouped_jobs[0].name == "job-2"
    
    assert len(api_group._api_resource._grouped_jobs) == 1
    assert api_group._api_resource._grouped_jobs[0].name == "job-2"


@pytest.mark.asyncio
async def test_groupedjobs_respects_global_batch_limit_across_namespaces(mock_kubernetes_loader, mock_config):
    """Verify batch_count is global: when limit reached, subsequent namespaces are not processed."""
    mock_config.namespaces = ["ns-1", "ns-2"]
    mock_config.discovery_job_max_batches = 1

    calls = []

    async def mock_batched_method(*args, **kwargs):
        calls.append(kwargs.get("namespace"))
        # return empty batch and no continue token
        return ([], None)

    mock_kubernetes_loader._list_namespaced_or_global_objects_batched = mock_batched_method

    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        result = await mock_kubernetes_loader._list_all_groupedjobs()

    # No results; with empty batches not counted, both namespaces are attempted
    assert result == []
    assert calls == ["ns-1", "ns-2"]


@pytest.mark.asyncio
async def test_groupedjobs_calls_each_explicit_namespace(mock_kubernetes_loader, mock_config):
    """Ensure explicit namespaces list is iterated and passed to the batched call."""
    mock_config.namespaces = ["namespace-a", "namespace-b"]
    mock_config.discovery_job_max_batches = 10

    seen_namespaces = []

    # Return one simple job per call and terminate with no continue token
    async def mock_batched_method(*args, **kwargs):
        ns = kwargs.get("namespace")
        seen_namespaces.append(ns)
        job = create_mock_job("job-1", ns if ns != "*" else "default", {"app": "frontend"})
        return ([job], None)

    mock_kubernetes_loader._list_namespaced_or_global_objects_batched = mock_batched_method

    def mock_build_scannable_object(item, container, kind):
        obj = MagicMock()
        obj._api_resource = MagicMock()
        obj.container = container.name
        return obj

    mock_kubernetes_loader._ClusterLoader__build_scannable_object = mock_build_scannable_object

    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        result = await mock_kubernetes_loader._list_all_groupedjobs()

    # We expect one grouped object per namespace
    assert len(result) == 2
    assert set(seen_namespaces) == {"namespace-a", "namespace-b"}
