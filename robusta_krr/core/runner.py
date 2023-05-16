import asyncio
import math
from typing import Optional, Union

from robusta_krr.core.abstract.strategies import ResourceRecommendation, RunResult
from robusta_krr.core.integrations.kubernetes import KubernetesLoader
from robusta_krr.core.integrations.prometheus import PrometheusLoader, PrometheusNotFound
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.result import ResourceAllocations, ResourceScan, ResourceType, Result
from robusta_krr.utils.configurable import Configurable
from robusta_krr.utils.logo import ASCII_LOGO
from robusta_krr.utils.version import get_version


class Runner(Configurable):
    EXPECTED_EXCEPTIONS = (KeyboardInterrupt, PrometheusNotFound)

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._k8s_loader = KubernetesLoader(self.config)
        self._prometheus_loaders: dict[Optional[str], Union[PrometheusLoader, Exception]] = {}
        self._prometheus_loaders_error_logged: set[Exception] = set()
        self._strategy = self.config.create_strategy()

    def _get_prometheus_loader(self, cluster: Optional[str]) -> Optional[PrometheusLoader]:
        if cluster not in self._prometheus_loaders:
            try:
                self._prometheus_loaders[cluster] = PrometheusLoader(self.config, cluster=cluster)
            except Exception as e:
                self._prometheus_loaders[cluster] = e

        result = self._prometheus_loaders[cluster]
        if isinstance(result, self.EXPECTED_EXCEPTIONS):
            if result not in self._prometheus_loaders_error_logged:
                self._prometheus_loaders_error_logged.add(result)
                self.error(result)
            return None
        elif isinstance(result, Exception):
            raise result

        return result

    def _greet(self) -> None:
        self.echo(ASCII_LOGO, no_prefix=True)
        self.echo(f"Running Robusta's KRR (Kubernetes Resource Recommender) {get_version()}", no_prefix=True)
        self.echo(f"Using strategy: {self._strategy}", no_prefix=True)
        self.echo(f"Using formatter: {self.config.format}", no_prefix=True)
        self.echo(no_prefix=True)

    def _process_result(self, result: Result) -> None:
        Formatter = self.config.Formatter
        formatted = result.format(Formatter)
        self.echo("\n", no_prefix=True)
        self.print_result(formatted, rich=Formatter.__rich_console__)

    def __get_resource_minimal(self, resource: ResourceType) -> float:
        if resource == ResourceType.CPU:
            return 1 / 1000 * self.config.cpu_min_value
        elif resource == ResourceType.Memory:
            return 1_000_000 * self.config.memory_min_value
        else:
            return 0

    def _round_value(self, value: Optional[float], resource: ResourceType) -> Optional[float]:
        if value is None or math.isnan(value):
            return value

        prec_power: Union[float, int]
        if resource == ResourceType.CPU:
            # NOTE: We use 10**3 as the minimal value for CPU is 1m
            prec_power = 10**3
        elif resource == ResourceType.Memory:
            # NOTE: We use 10**6 as the minimal value for memory is 1M
            prec_power = 1 / 10**6
        else:
            # NOTE: We use 1 as the minimal value for other resources
            prec_power = 1

        rounded = math.ceil(value * prec_power) / prec_power

        minimal = self.__get_resource_minimal(resource)
        return max(rounded, minimal)

    def _format_result(self, result: RunResult) -> RunResult:
        return {
            resource: ResourceRecommendation(
                request=self._round_value(recommendation.request, resource),
                limit=self._round_value(recommendation.limit, resource),
            )
            for resource, recommendation in result.items()
        }

    async def _calculate_object_recommendations(self, object: K8sObjectData) -> RunResult:
        prometheus_loader = self._get_prometheus_loader(object.cluster)

        if prometheus_loader is None:
            return {resource: ResourceRecommendation.undefined() for resource in ResourceType}

        data_tuple = await asyncio.gather(
            *[
                prometheus_loader.gather_data(
                    object,
                    resource,
                    self._strategy.settings.history_timedelta,
                    step=self._strategy.settings.timeframe_timedelta,
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
        self.info(f'Using clusters: {clusters if clusters is not None else "inner cluster"}')
        objects = await self._k8s_loader.list_scannable_objects(clusters)

        if len(objects) == 0:
            self.warning("Current filters resulted in no objects available to scan.")
            self.warning("Try to change the filters or check if there is anything available.")
            if self.config.namespaces == "*":
                self.warning("Note that you are using the '*' namespace filter, which by default excludes kube-system.")
            return Result(scans=[])

        resource_recommendations = await self._gather_objects_recommendations(objects)

        return Result(
            scans=[
                ResourceScan.calculate(obj, recommended) for obj, recommended in zip(objects, resource_recommendations)
            ],
            description=self._strategy.description,
        )

    async def run(self) -> None:
        self._greet()
        try:
            result = await self._collect_result()
            self._process_result(result)
        except Exception:
            self.console.print_exception(extra_lines=1, max_frames=10)
