import asyncio
import math
from decimal import Decimal

from robusta_krr.core.abstract.strategies import ResourceRecommendation, RunResult
from robusta_krr.core.integrations.kubernetes import KubernetesLoader
from robusta_krr.core.integrations.prometheus import PrometheusLoader
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.result import ResourceAllocations, ResourceScan, ResourceType, Result
from robusta_krr.utils.configurable import Configurable
from robusta_krr.utils.logo import ASCII_LOGO
from robusta_krr.utils.version import get_version


class Runner(Configurable):
    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._k8s_loader = KubernetesLoader(self.config)
        self._prometheus_loaders: dict[str, PrometheusLoader | Exception] = {}
        self._strategy = self.config.create_strategy()

    def _get_prometheus_loader(self, cluster: str) -> PrometheusLoader:
        if cluster not in self._prometheus_loaders:
            try:
                self._prometheus_loaders[cluster] = PrometheusLoader(self.config, cluster=cluster)
            except Exception as e:
                self._prometheus_loaders[cluster] = e

        result = self._prometheus_loaders[cluster]
        if isinstance(result, Exception):
            raise result

        return result

    def _greet(self) -> None:
        self.echo(ASCII_LOGO, no_prefix=True)
        self.echo(f"Running Robusta's KRR (Kubernetes Resource Recommender) {get_version()}", no_prefix=True)
        self.echo(f"Using strategy: {self._strategy}", no_prefix=True)
        self.echo(f"Using formatter: {self.config.format}", no_prefix=True)
        self.echo(no_prefix=True)

    def _process_result(self, result: Result) -> None:
        formatted = result.format(self.config.format)
        self.echo("\n", no_prefix=True)
        self.console.print(formatted)

    @staticmethod
    def _round_value(value: Decimal | None) -> Decimal | None:
        if value is None or value.is_nan():
            return None

        return Decimal(math.ceil(value * 1000)) / 1000

    @staticmethod
    def _format_result(result: RunResult) -> RunResult:
        return {
            resource: ResourceRecommendation(
                request=Runner._round_value(recommendation.request),
                limit=Runner._round_value(recommendation.limit),
            )
            for resource, recommendation in result.items()
        }

    async def _calculate_object_recommendations(self, object: K8sObjectData) -> RunResult:
        prometheus_loader = self._get_prometheus_loader(object.cluster)

        data_tuple = await asyncio.gather(
            *[
                prometheus_loader.gather_data(
                    object,
                    resource,
                    self._strategy.settings.history_timedelta,
                )
                for resource in ResourceType
            ]
        )
        data = dict(zip(ResourceType, data_tuple))

        # NOTE: We run this in a threadpool as the strategy calculation might be CPU intensive
        # But keep in mind that numpy calcluations will not block the GIL
        result = await asyncio.to_thread(self._strategy.run, data, object)
        return self._format_result(result)

    async def _gather_objects_recommendations(self, objects: list[K8sObjectData]) -> list[ResourceAllocations]:
        recommendations: list[RunResult] = await asyncio.gather(
            *[self._calculate_object_recommendations(object) for object in objects]
        )

        return [
            ResourceAllocations(
                requests={resource: recommendation[resource].request for resource in ResourceType},
                limits={resource: recommendation[resource].limit for resource in ResourceType},
            )
            for recommendation in recommendations
        ]

    async def _collect_result(self) -> Result:
        clusters = await self._k8s_loader.list_clusters()
        self.debug(f'Using clusters: {", ".join(clusters)}')
        objects = await self._k8s_loader.list_scannable_objects(clusters)
        resource_recommendations = await self._gather_objects_recommendations(objects)

        return Result(
            scans=[
                ResourceScan(object=obj, recommended=recommended)
                for obj, recommended in zip(objects, resource_recommendations)
            ]
        )

    async def run(self) -> None:
        self._greet()
        result = await self._collect_result()
        self._process_result(result)
