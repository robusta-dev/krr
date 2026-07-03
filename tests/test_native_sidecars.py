"""Tests for native-sidecar discovery.

KRR right-sizes native sidecars (init containers with ``restartPolicy: Always``,
GA in Kubernetes 1.29) like normal containers, while intentionally ignoring
one-shot init containers. The core logic lives in the module-level helper
``_native_sidecars``; these tests cover it directly (it is pure) plus two
discovery paths that use it (the Deployment extractor lambda and the Job loop).

Typed kubernetes-client models are simulated with ``SimpleNamespace`` rather than
``MagicMock`` on purpose: ``MagicMock`` auto-creates any attribute, so
``getattr(mock, "initContainers", None)`` would return a truthy mock and defeat
the snake_case/camelCase fallback under test. CRD workloads are simulated with a
real ``ObjectLikeDict`` (raw camelCase keys), exactly as the custom-objects API
returns them.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from robusta_krr.core.integrations.kubernetes import ClusterLoader, _native_sidecars
from robusta_krr.core.models.config import Config
from robusta_krr.utils.object_like_dict import ObjectLikeDict


def typed_container(name: str, **kwargs) -> SimpleNamespace:
    """A typed V1Container-like object. Pass restart_policy=... to set it;
    omit it entirely to simulate an old client where the field does not exist."""
    return SimpleNamespace(name=name, **kwargs)


def typed_spec(containers, init_containers=None) -> SimpleNamespace:
    """A typed V1PodSpec-like object (snake_case attributes)."""
    return SimpleNamespace(containers=containers, init_containers=init_containers)


# --- pure helper tests -------------------------------------------------------


def test_native_sidecar_discovered():
    spec = typed_spec(
        containers=[typed_container("main")],
        init_containers=[typed_container("proxy", restart_policy="Always")],
    )
    sidecars = _native_sidecars(spec)
    assert [c.name for c in sidecars] == ["proxy"]


def test_oneshot_init_container_excluded():
    # A one-shot init container has restart_policy unset (None) -> not a sidecar.
    spec = typed_spec(
        containers=[typed_container("main")],
        init_containers=[typed_container("db-migrate", restart_policy=None)],
    )
    assert _native_sidecars(spec) == []


def test_no_init_containers():
    spec = typed_spec(containers=[typed_container("main")], init_containers=None)
    assert _native_sidecars(spec) == []


def test_none_pod_spec():
    # Guards the Rollout workloadRef branch and any spec-less edge.
    assert _native_sidecars(None) == []


def test_old_client_no_restart_policy_field():
    # On kubernetes < 28.1.0 the container model has no restart_policy attribute
    # at all: the helper must degrade to a no-op, not crash.
    spec = typed_spec(
        containers=[typed_container("main")],
        init_containers=[typed_container("maybe-sidecar")],  # no restart_policy attr
    )
    assert _native_sidecars(spec) == []


def test_crd_camelcase_sidecar():
    # Custom-objects API (Rollout/StrimziPodSet/DeploymentConfig) returns raw
    # camelCase keys wrapped in ObjectLikeDict.
    spec = ObjectLikeDict(
        {
            "containers": [{"name": "main"}],
            "initContainers": [
                {"name": "proxy", "restartPolicy": "Always"},
                {"name": "warmup", "restartPolicy": None},
            ],
        }
    )
    sidecars = _native_sidecars(spec)
    assert [c.name for c in sidecars] == ["proxy"]


def test_mixed_init_containers():
    spec = typed_spec(
        containers=[typed_container("main")],
        init_containers=[
            typed_container("db-migrate", restart_policy=None),
            typed_container("proxy", restart_policy="Always"),
            typed_container("logshipper", restart_policy="Always"),
        ],
    )
    assert [c.name for c in _native_sidecars(spec)] == ["proxy", "logshipper"]


# --- integration tests through real discovery paths --------------------------


@pytest.fixture
def mock_config():
    config = MagicMock(spec=Config)
    config.resources = "*"
    config.selector = None
    config.namespaces = "*"
    config.max_workers = 4
    config.get_kube_client = MagicMock()
    # Job discovery settings
    config.discovery_job_batch_size = 1000
    config.discovery_job_max_batches = 50
    return config


@pytest.fixture
def loader(mock_config):
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        loader = ClusterLoader()
        loader.apps = MagicMock()
        loader.batch = MagicMock()
        loader.core = MagicMock()

        # __build_scannable_object is name-mangled; stub it to expose container name.
        def build(item, container, kind):
            obj = MagicMock()
            obj.container = container.name
            obj.kind = kind
            return obj

        loader._ClusterLoader__build_scannable_object = build  # type: ignore
        return loader


@pytest.mark.asyncio
async def test_deployment_extractor_includes_sidecar(loader, mock_config):
    """The real Deployment extractor lambda + _list_scannable_objects yields the
    main container and the native sidecar, but not the one-shot init container."""
    deployment = SimpleNamespace(
        spec=SimpleNamespace(
            template=SimpleNamespace(
                spec=typed_spec(
                    containers=[typed_container("web")],
                    init_containers=[
                        typed_container("php-fpm", restart_policy="Always"),
                        typed_container("db-migrate", restart_policy=None),
                    ],
                )
            )
        )
    )
    loader._list_namespaced_or_global_objects = AsyncMock(return_value=[deployment])

    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        result = await loader._list_deployments()

    assert {obj.container for obj in result} == {"web", "php-fpm"}


@pytest.mark.asyncio
async def test_job_includes_native_sidecar(loader, mock_config):
    """The Job loop (which bypasses _list_scannable_objects) also picks up the
    native sidecar and skips the one-shot init container."""
    job = MagicMock()
    job.metadata.owner_references = []
    job.metadata.labels = {}
    job.spec.template.spec = typed_spec(
        containers=[typed_container("batch")],
        init_containers=[
            typed_container("metrics", restart_policy="Always"),
            typed_container("seed", restart_policy=None),
        ],
    )

    async def batched(*args, **kwargs):
        return ([job], None)

    loader._list_namespaced_or_global_objects_batched = batched
    loader._is_job_owned_by_cronjob = MagicMock(return_value=False)
    loader._is_job_grouped = MagicMock(return_value=False)

    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        result = await loader._list_all_jobs()

    assert {obj.container for obj in result} == {"batch", "metrics"}
