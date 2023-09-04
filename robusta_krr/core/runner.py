import asyncio
import math
import os
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Union

from prometrix import PrometheusNotFound
from slack_sdk import WebClient

from robusta_krr.core.abstract.strategies import ResourceRecommendation, RunResult
from robusta_krr.core.integrations.kubernetes import KubernetesLoader
from robusta_krr.core.integrations.prometheus import ClusterNotSpecifiedException, PrometheusMetricsLoader
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.result import ResourceAllocations, ResourceScan, ResourceType, Result, StrategyData
from robusta_krr.utils.configurable import Configurable
from robusta_krr.utils.logo import ASCII_LOGO
from robusta_krr.utils.progress_bar import ProgressBar
from robusta_krr.utils.version import get_version


class Runner(Configurable):
    EXPECTED_EXCEPTIONS = (KeyboardInterrupt, PrometheusNotFound)

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._k8s_loader = KubernetesLoader(self.config)
        self._metrics_service_loaders: dict[Optional[str], Union[PrometheusMetricsLoader, Exception]] = {}
        self._metrics_service_loaders_error_logged: set[Exception] = set()
        self._strategy = self.config.create_strategy()
        
        # This executor will be running calculations for recommendations
        self._executor = ThreadPoolExecutor(self.config.max_workers)

    def _get_prometheus_loader(self, cluster: Optional[str]) -> Optional[PrometheusMetricsLoader]:
        if cluster not in self._metrics_service_loaders:
            try:
                self._metrics_service_loaders[cluster] = PrometheusMetricsLoader(self.config, cluster=cluster)
            except Exception as e:
                self._metrics_service_loaders[cluster] = e

        result = self._metrics_service_loaders[cluster]
        if isinstance(result, self.EXPECTED_EXCEPTIONS):
            if result not in self._metrics_service_loaders_error_logged:
                self._metrics_service_loaders_error_logged.add(result)
                self.error(str(result))
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
        self.print_result(formatted, rich=getattr(Formatter, "__rich_console__", False))
        if (self.config.file_output) or (self.config.slack_output):
            if self.config.file_output:
                file_name = self.config.file_output
            elif self.config.slack_output:
                file_name = self.config.slack_output
            with open(file_name, "w") as target_file:
                sys.stdout = target_file
                self.print_result(formatted, rich=getattr(Formatter, "__rich_console__", False))
                sys.stdout = sys.stdout
            if self.config.slack_output:
                client = WebClient(os.environ["SLACK_BOT_TOKEN"])
                warnings.filterwarnings("ignore", category=UserWarning)
                client.files_upload(
                    channels=f"#{self.config.slack_output}",
                    title="KRR Report",
                    file=f"./{file_name}",
                    initial_comment=f'Kubernetes Resource Report for {(" ".join(self.config.namespaces))}',
                )
                os.remove(file_name)

    def __get_resource_minimal(self, resource: ResourceType) -> float:
        if resource == ResourceType.CPU:
            return 1 / 1000 * self.config.cpu_min_value
        elif resource == ResourceType.Memory:
            return 1024**2 * self.config.memory_min_value
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
            prec_power = 1 / (1024**2)
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
                info=recommendation.info,
            )
            for resource, recommendation in result.items()
        }

    async def _calculate_object_recommendations(self, object: K8sObjectData) -> RunResult:
        prometheus_loader = self._get_prometheus_loader(object.cluster)

        if prometheus_loader is None:
            return {resource: ResourceRecommendation.undefined() for resource in ResourceType}

        metrics = await prometheus_loader.gather_data(
            object,
            self._strategy,
            self._strategy.settings.history_timedelta,
            step=self._strategy.settings.timeframe_timedelta,
        )

        self.debug(f"Calculating recommendations for {object} with {len(metrics)} metrics")

        # NOTE: We run this in a threadpool as the strategy calculation might be CPU intensive
        # But keep in mind that numpy calcluations will not block the GIL
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(self._executor, self._strategy.run, metrics, object)
        return self._format_result(result)

    async def _gather_object_allocations(self, k8s_object: K8sObjectData) -> ResourceScan:
        recommendation = await self._calculate_object_recommendations(k8s_object)

        self.__progressbar.progress()

        return ResourceScan.calculate(
            k8s_object,
            ResourceAllocations(
                requests={resource: recommendation[resource].request for resource in ResourceType},
                limits={resource: recommendation[resource].limit for resource in ResourceType},
                info={resource: recommendation[resource].info for resource in ResourceType},
            ),
        )

    async def _collect_result(self) -> Result:
        clusters = await self._k8s_loader.list_clusters()
        if clusters and len(clusters) > 1 and self.config.prometheus_url:
            # this can only happen for multi-cluster querying a single centeralized prometheus
            # In this scenario we dont yet support determining which metrics belong to which cluster so the reccomendation can be incorrect
            raise ClusterNotSpecifiedException(
                f"Cannot scan multiple clusters for this prometheus, Rerun with the flag `-c <cluster>` where <cluster> is one of {clusters}"
            )

        self.info(f'Using clusters: {clusters if clusters is not None else "inner cluster"}')

        with ProgressBar(self.config, title="Calculating Recommendation") as self.__progressbar:
            scans_tasks = [
                asyncio.create_task(self._gather_object_allocations(k8s_object))
                async for k8s_object in self._k8s_loader.list_scannable_objects(clusters)
            ]

            scans = await asyncio.gather(*scans_tasks)

        if len(scans) == 0:
            self.warning("Current filters resulted in no objects available to scan.")
            self.warning("Try to change the filters or check if there is anything available.")
            if self.config.namespaces == "*":
                self.warning("Note that you are using the '*' namespace filter, which by default excludes kube-system.")
            return Result(
                scans=[],
                strategy=StrategyData(name=str(self._strategy).lower(), settings=self._strategy.settings.dict()),
            )

        return Result(
            scans=scans,
            description=self._strategy.description,
            strategy=StrategyData(
                name=str(self._strategy).lower(),
                settings=self._strategy.settings.dict(),
            ),
        )

    async def run(self) -> None:
        self._greet()

        try:
            self.config.load_kubeconfig()
        except Exception as e:
            self.error(f"Could not load kubernetes configuration: {e}")
            self.error("Try to explicitly set --context and/or --kubeconfig flags.")
            return

        try:
            # eks has a lower step limit than other types of prometheus, it will throw an error
            step_count = self._strategy.settings.history_duration * 60 / self._strategy.settings.timeframe_duration
            if self.config.eks_managed_prom and step_count > 10000:
                min_step = self._strategy.settings.history_duration * 60 / 10000 
                self.warning(f"The timeframe duration provided is insufficient and will be overridden with {min_step}. Kindly adjust --timeframe_duration to a value equal to or greater than {min_step}.")
                self._strategy.settings.timeframe_duration = min_step

            result = await self._collect_result()
            self._process_result(result)
        except ClusterNotSpecifiedException as e:
            self.error(e)
        except Exception:
            self.console.print_exception(extra_lines=1, max_frames=10)
