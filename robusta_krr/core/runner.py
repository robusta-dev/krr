import asyncio
import itertools

from robusta_krr.core.config import Config
from robusta_krr.core.kubernetes import KubernetesLoader
from robusta_krr.core.objects import K8sObjectData
from robusta_krr.core.prometheus import PrometheusLoader
from robusta_krr.core.result import ResourceAllocations, ResourceScan, ResourceType, Result
from robusta_krr.core.strategies import ResourceRecommendation
from robusta_krr.utils.configurable import Configurable
from robusta_krr.utils.version import get_version
from robusta_krr.utils.logo import ASCII_LOGO


class Runner(Configurable):
    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._k8s_loader = KubernetesLoader(self.config)
        self._prometheus_loader = PrometheusLoader(self.config)
        self._strategy = self.config.create_strategy()

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

    async def _gather_objects_current_allocations(self, objects: list[K8sObjectData]) -> list[ResourceAllocations]:
        return await asyncio.gather(*[self._k8s_loader.get_object_current_recommendations(obj) for obj in objects])

    async def _calculate_object_recommendations(
        self, object: K8sObjectData, resource: ResourceType
    ) -> ResourceRecommendation:
        data = await self._prometheus_loader.gather_data(
            object,
            resource,
            self._strategy.settings.history_timedelta,
        )

        # NOTE: We run this in a threadpool as the strategy calculation might be CPU intensive
        # TODO: Maybe we should do it in a processpool instead?
        # But keep in mind that numpy calcluations will not block the GIL
        return await asyncio.to_thread(self._strategy.run, data, object, resource)

    async def _gather_objects_recommendations(self, objects: list[K8sObjectData]) -> list[ResourceAllocations]:
        recommendations: list[ResourceRecommendation] = await asyncio.gather(
            *[
                self._calculate_object_recommendations(object, resource)
                for object, resource in itertools.product(objects, ResourceType)
            ]
        )
        recommendations_dict = dict(zip(itertools.product(objects, ResourceType), recommendations))

        return [
            ResourceAllocations(
                requests={resource: recommendations_dict[object, resource].request for resource in ResourceType},
                limits={resource: recommendations_dict[object, resource].limit for resource in ResourceType},
            )
            for object in objects
        ]

    async def _collect_result(self) -> Result:
        objects = await self._k8s_loader.list_scannable_objects()
        async with asyncio.TaskGroup() as tg:
            current_allocations_task = tg.create_task(self._gather_objects_current_allocations(objects))
            resource_recommendations_task = tg.create_task(self._gather_objects_recommendations(objects))

        return Result(
            scans=[
                ResourceScan(object=obj, current=current, recommended=recommended)
                for obj, current, recommended in zip(
                    objects, current_allocations_task.result(), resource_recommendations_task.result()
                )
            ]
        )

    async def run(self) -> None:
        self._greet()
        result = await self._collect_result()
        self._process_result(result)
