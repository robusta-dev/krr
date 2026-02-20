"""
Tests for initContainer support in KRR.

Verifies that init_containers are properly extracted alongside regular containers
for all 9 supported workload types.

Also tests the dual snake_case/camelCase handling for CustomObjectsApi workloads.
"""

import pytest
from unittest.mock import MagicMock, patch
from robusta_krr.core.integrations.kubernetes import ClusterLoader, _get_init_containers
from robusta_krr.core.models.config import Config
from robusta_krr.utils.object_like_dict import ObjectLikeDict


@pytest.fixture
def mock_config():
    """Mock config for testing"""
    config = MagicMock(spec=Config)
    config.job_grouping_labels = []
    config.job_grouping_limit = 10
    config.discovery_job_batch_size = 1000
    config.discovery_job_max_batches = 50
    config.max_workers = 4
    config.get_kube_client = MagicMock()
    config.resources = "*"
    config.selector = None
    config.namespaces = "*"
    return config


@pytest.fixture
def mock_cluster_loader(mock_config):
    """Create a ClusterLoader instance with mocked dependencies"""
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        loader = ClusterLoader()
        loader.apps = MagicMock()
        loader.batch = MagicMock()
        loader.core = MagicMock()
        loader.custom_objects = MagicMock()
        loader._ClusterLoader__hpa_list = {}

        # Mock executor
        from concurrent.futures import Future

        mock_future = Future()
        mock_future.set_result(None)
        loader.executor = MagicMock()
        loader.executor.submit.return_value = mock_future

        return loader


def create_mock_container(name: str):
    """Create a mock container object"""
    container = MagicMock()
    container.name = name
    container.resources = MagicMock()
    container.resources.requests = {"cpu": "100m", "memory": "128Mi"}
    container.resources.limits = {"cpu": "200m", "memory": "256Mi"}
    return container


def create_mock_deployment(name: str, namespace: str, containers: list, init_containers: list | None = None):
    """Create a mock Deployment with containers and optional init_containers"""
    deployment = MagicMock()
    deployment.metadata.name = name
    deployment.metadata.namespace = namespace
    deployment.metadata.labels = {"app": name}
    deployment.metadata.annotations = {}
    deployment.spec.template.spec.containers = containers
    deployment.spec.template.spec.init_containers = init_containers
    deployment.spec.selector = MagicMock()
    deployment.spec.selector.match_labels = {"app": name}
    deployment.spec.selector.match_expressions = None
    return deployment


def create_mock_job(name: str, namespace: str, containers: list, init_containers: list | None = None):
    """Create a mock Job with containers and optional init_containers"""
    job = MagicMock()
    job.metadata.name = name
    job.metadata.namespace = namespace
    job.metadata.labels = {"app": name}
    job.metadata.annotations = {}
    job.metadata.owner_references = []
    job.spec.template.spec.containers = containers
    job.spec.template.spec.init_containers = init_containers
    return job


def create_mock_cronjob(name: str, namespace: str, containers: list, init_containers: list | None = None):
    """Create a mock CronJob with containers and optional init_containers"""
    cronjob = MagicMock()
    cronjob.metadata.name = name
    cronjob.metadata.namespace = namespace
    cronjob.metadata.labels = {"app": name}
    cronjob.metadata.annotations = {}
    cronjob.spec.job_template.spec.template.spec.containers = containers
    cronjob.spec.job_template.spec.template.spec.init_containers = init_containers
    cronjob.spec.selector = MagicMock()
    cronjob.spec.selector.match_labels = {"app": name}
    cronjob.spec.selector.match_expressions = None
    return cronjob


# Helper functions to match the extract_containers patterns used in the main code
def extract_deployment_containers(item):
    """Extract containers from Deployment/StatefulSet/DaemonSet (standard pattern)"""
    return item.spec.template.spec.containers + (item.spec.template.spec.init_containers or [])


def extract_cronjob_containers(item):
    """Extract containers from CronJob (job_template path)"""
    return item.spec.job_template.spec.template.spec.containers + (
        item.spec.job_template.spec.template.spec.init_containers or []
    )


def extract_strimzipodset_containers(item):
    """Extract containers from StrimziPodSet (pods[0] path)"""
    return item.spec.pods[0].spec.containers + (item.spec.pods[0].spec.init_containers or [])


class TestInitContainerExtraction:
    """Test that init_containers are properly extracted from workloads using direct lambda tests"""

    def test_deployment_extract_with_initcontainers(self):
        """Test that Deployment extract lambda includes both containers and init_containers"""
        main_container = create_mock_container("main-app")
        init_container = create_mock_container("init-db")

        deployment = create_mock_deployment(
            "test-deployment", "default", containers=[main_container], init_containers=[init_container]
        )

        result = extract_deployment_containers(deployment)
        assert len(result) == 2
        container_names = {c.name for c in result}
        assert "main-app" in container_names
        assert "init-db" in container_names

    def test_deployment_extract_without_initcontainers(self):
        """Test that Deployment extract lambda works when init_containers is None"""
        main_container = create_mock_container("main-app")

        deployment = create_mock_deployment(
            "test-deployment", "default", containers=[main_container], init_containers=None
        )

        result = extract_deployment_containers(deployment)
        assert len(result) == 1
        assert result[0].name == "main-app"

    def test_deployment_extract_with_empty_initcontainers(self):
        """Test that Deployment extract lambda works when init_containers is empty list"""
        main_container = create_mock_container("main-app")

        deployment = create_mock_deployment(
            "test-deployment", "default", containers=[main_container], init_containers=[]
        )

        result = extract_deployment_containers(deployment)
        assert len(result) == 1
        assert result[0].name == "main-app"

    def test_deployment_extract_with_multiple_initcontainers(self):
        """Test Deployment extract lambda with multiple init_containers"""
        main_container = create_mock_container("main-app")
        init_container1 = create_mock_container("init-db")
        init_container2 = create_mock_container("init-cache")
        init_container3 = create_mock_container("init-config")

        deployment = create_mock_deployment(
            "test-deployment",
            "default",
            containers=[main_container],
            init_containers=[init_container1, init_container2, init_container3],
        )

        result = extract_deployment_containers(deployment)
        assert len(result) == 4
        container_names = {c.name for c in result}
        assert container_names == {"main-app", "init-db", "init-cache", "init-config"}


class TestCronJobInitContainers:
    """Test initContainer extraction for CronJobs (different spec path)"""

    def test_cronjob_extract_with_initcontainers(self):
        """Test that CronJob extract lambda includes init_containers from job_template path"""
        main_container = create_mock_container("cron-task")
        init_container = create_mock_container("init-setup")

        cronjob = create_mock_cronjob(
            "test-cronjob", "default", containers=[main_container], init_containers=[init_container]
        )

        result = extract_cronjob_containers(cronjob)
        assert len(result) == 2
        container_names = {c.name for c in result}
        assert "cron-task" in container_names
        assert "init-setup" in container_names

    def test_cronjob_extract_without_initcontainers(self):
        """Test CronJob extract lambda when init_containers is None"""
        main_container = create_mock_container("cron-task")

        cronjob = create_mock_cronjob("test-cronjob", "default", containers=[main_container], init_containers=None)

        result = extract_cronjob_containers(cronjob)
        assert len(result) == 1
        assert result[0].name == "cron-task"


class TestJobInitContainers:
    """Test initContainer extraction for Jobs (uses inline loop)"""

    @pytest.mark.asyncio
    async def test_job_with_initcontainers(self, mock_cluster_loader, mock_config):
        """Test that Job extracts both containers and init_containers via inline loop"""
        main_container = create_mock_container("job-worker")
        init_container = create_mock_container("init-data")

        job = create_mock_job("test-job", "default", containers=[main_container], init_containers=[init_container])

        # Mock the batched method
        async def mock_batched_method(*args, **kwargs):
            return ([job], None)

        mock_cluster_loader._list_namespaced_or_global_objects_batched = mock_batched_method

        # Mock _is_job_owned_by_cronjob and _is_job_grouped
        mock_cluster_loader._is_job_owned_by_cronjob = MagicMock(return_value=False)
        mock_cluster_loader._is_job_grouped = MagicMock(return_value=False)

        with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
            result = await mock_cluster_loader._list_all_jobs()

        # Should find 2 containers (1 main + 1 init)
        assert len(result) == 2
        container_names = {r.container for r in result}
        assert "job-worker" in container_names
        assert "init-data" in container_names

    @pytest.mark.asyncio
    async def test_job_without_initcontainers(self, mock_cluster_loader, mock_config):
        """Test that Job works when init_containers is None"""
        main_container = create_mock_container("job-worker")

        job = create_mock_job("test-job", "default", containers=[main_container], init_containers=None)

        async def mock_batched_method(*args, **kwargs):
            return ([job], None)

        mock_cluster_loader._list_namespaced_or_global_objects_batched = mock_batched_method
        mock_cluster_loader._is_job_owned_by_cronjob = MagicMock(return_value=False)
        mock_cluster_loader._is_job_grouped = MagicMock(return_value=False)

        with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
            result = await mock_cluster_loader._list_all_jobs()

        assert len(result) == 1
        assert result[0].container == "job-worker"


class TestGroupedJobInitContainers:
    """Test initContainer extraction for GroupedJobs"""

    @pytest.mark.asyncio
    async def test_groupedjob_with_initcontainers(self, mock_cluster_loader, mock_config):
        """Test that GroupedJob extracts init_containers"""
        mock_config.job_grouping_labels = ["app"]

        main_container = create_mock_container("worker")
        init_container = create_mock_container("init-setup")

        job = create_mock_job("test-job-1", "default", containers=[main_container], init_containers=[init_container])
        job.metadata.labels = {"app": "test-app"}

        async def mock_batched_method(*args, **kwargs):
            return ([job], None)

        mock_cluster_loader._list_namespaced_or_global_objects_batched = mock_batched_method
        mock_cluster_loader._is_job_owned_by_cronjob = MagicMock(return_value=False)
        mock_cluster_loader._is_job_grouped = MagicMock(return_value=True)

        with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
            result = await mock_cluster_loader._list_all_groupedjobs()

        # Should find 2 GroupedJob objects (one per container name)
        assert len(result) == 2
        container_names = {r.container for r in result}
        assert "worker" in container_names
        assert "init-setup" in container_names


class TestExtractContainersLambda:
    """Unit tests for the extract_containers lambda patterns"""

    def test_standard_pattern_with_initcontainers(self):
        """Test the standard lambda pattern includes init_containers"""
        mock_item = MagicMock()
        mock_item.spec.template.spec.containers = [create_mock_container("main")]
        mock_item.spec.template.spec.init_containers = [create_mock_container("init")]

        result = extract_deployment_containers(mock_item)
        assert len(result) == 2

    def test_standard_pattern_with_none_initcontainers(self):
        """Test the standard lambda pattern handles None init_containers"""
        mock_item = MagicMock()
        mock_item.spec.template.spec.containers = [create_mock_container("main")]
        mock_item.spec.template.spec.init_containers = None

        result = extract_deployment_containers(mock_item)
        assert len(result) == 1

    def test_cronjob_pattern_with_initcontainers(self):
        """Test the CronJob lambda pattern includes init_containers"""
        mock_item = MagicMock()
        mock_item.spec.job_template.spec.template.spec.containers = [create_mock_container("cron-main")]
        mock_item.spec.job_template.spec.template.spec.init_containers = [create_mock_container("cron-init")]

        result = extract_cronjob_containers(mock_item)
        assert len(result) == 2

    def test_strimzipodset_pattern_with_initcontainers(self):
        """Test the StrimziPodSet lambda pattern includes init_containers"""
        mock_item = MagicMock()
        mock_item.spec.pods = [MagicMock()]
        mock_item.spec.pods[0].spec.containers = [create_mock_container("kafka")]
        mock_item.spec.pods[0].spec.init_containers = [create_mock_container("init-kafka")]

        result = extract_strimzipodset_containers(mock_item)
        assert len(result) == 2


class TestGetInitContainersHelper:
    """Tests for the _get_init_containers helper function that handles snake_case/camelCase"""

    def test_snake_case_init_containers(self):
        """Test that snake_case init_containers is found (standard K8s Python client)"""
        spec = MagicMock()
        spec.init_containers = [create_mock_container("init-db")]

        result = _get_init_containers(spec)
        assert len(result) == 1
        assert result[0].name == "init-db"

    def test_camel_case_initContainers(self):
        """Test that camelCase initContainers is found (CustomObjectsApi)"""
        # Simulate ObjectLikeDict behavior where snake_case returns None
        spec = MagicMock()
        spec.init_containers = None  # snake_case not present
        spec.initContainers = [create_mock_container("init-setup")]

        result = _get_init_containers(spec)
        assert len(result) == 1
        assert result[0].name == "init-setup"

    def test_neither_present_returns_empty(self):
        """Test that empty list is returned when neither attribute exists"""
        spec = MagicMock()
        spec.init_containers = None
        spec.initContainers = None

        result = _get_init_containers(spec)
        assert result == []

    def test_snake_case_takes_precedence(self):
        """Test that snake_case is checked first when both exist"""
        spec = MagicMock()
        spec.init_containers = [create_mock_container("snake-init")]
        spec.initContainers = [create_mock_container("camel-init")]

        result = _get_init_containers(spec)
        assert len(result) == 1
        assert result[0].name == "snake-init"

    def test_empty_snake_case_returns_empty(self):
        """Test that empty list from snake_case is returned (not fallback to camelCase)"""
        spec = MagicMock()
        spec.init_containers = []  # Empty but not None
        spec.initContainers = [create_mock_container("camel-init")]

        result = _get_init_containers(spec)
        assert result == []


class TestCustomObjectsApiCamelCase:
    """Tests for CustomObjectsApi workloads that use camelCase (initContainers)"""

    def test_rollout_with_camelcase_initcontainers(self):
        """Test Rollout extraction with camelCase initContainers (CustomObjectsApi)"""
        # Simulate ObjectLikeDict from CustomObjectsApi - uses camelCase
        rollout_dict = {
            "metadata": {"name": "test-rollout", "namespace": "default"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"name": "main-app", "resources": {}}],
                        "initContainers": [{"name": "init-setup", "resources": {}}],
                    }
                }
            },
        }
        item = ObjectLikeDict(rollout_dict)

        # Use the helper function as the implementation does
        result = item.spec.template.spec.containers + _get_init_containers(item.spec.template.spec)
        assert len(result) == 2
        container_names = {c.name if hasattr(c, "name") else c["name"] for c in result}
        assert "main-app" in container_names
        assert "init-setup" in container_names

    def test_rollout_without_initcontainers(self):
        """Test Rollout extraction when initContainers is not present"""
        rollout_dict = {
            "metadata": {"name": "test-rollout", "namespace": "default"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"name": "main-app", "resources": {}}],
                    }
                }
            },
        }
        item = ObjectLikeDict(rollout_dict)

        result = item.spec.template.spec.containers + _get_init_containers(item.spec.template.spec)
        assert len(result) == 1

    def test_strimzipodset_with_camelcase_initcontainers(self):
        """Test StrimziPodSet extraction with camelCase initContainers"""
        strimzi_dict = {
            "metadata": {"name": "kafka-cluster", "namespace": "kafka"},
            "spec": {
                "pods": [
                    {
                        "spec": {
                            "containers": [{"name": "kafka", "resources": {}}],
                            "initContainers": [{"name": "init-kafka", "resources": {}}],
                        }
                    }
                ]
            },
        }
        item = ObjectLikeDict(strimzi_dict)

        result = item.spec.pods[0].spec.containers + _get_init_containers(item.spec.pods[0].spec)
        assert len(result) == 2
        container_names = {c.name if hasattr(c, "name") else c["name"] for c in result}
        assert "kafka" in container_names
        assert "init-kafka" in container_names

    def test_deploymentconfig_with_camelcase_initcontainers(self):
        """Test DeploymentConfig extraction with camelCase initContainers"""
        dc_dict = {
            "metadata": {"name": "myapp-dc", "namespace": "openshift-project"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{"name": "app", "resources": {}}],
                        "initContainers": [{"name": "init-config", "resources": {}}],
                    }
                }
            },
        }
        item = ObjectLikeDict(dc_dict)

        result = item.spec.template.spec.containers + _get_init_containers(item.spec.template.spec)
        assert len(result) == 2
        container_names = {c.name if hasattr(c, "name") else c["name"] for c in result}
        assert "app" in container_names
        assert "init-config" in container_names

    def test_objectlikedict_returns_none_for_missing_attr(self):
        """Verify ObjectLikeDict returns None for missing attributes (the root cause)"""
        obj_dict = {"containers": [{"name": "main"}]}
        obj = ObjectLikeDict(obj_dict)

        # This is the behavior that caused the original bug
        assert obj.init_containers is None  # snake_case - not in dict
        assert obj.initContainers is None  # camelCase - also not in dict
        assert obj.containers is not None  # This key exists
