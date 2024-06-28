import asyncio
import itertools
import logging
import math
import os
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Union
from datetime import timedelta
from rich.console import Console
from slack_sdk import WebClient
from prometrix import PrometheusNotFound

from robusta_krr.core.abstract.strategies import ResourceRecommendation, RunResult
from robusta_krr.core.abstract.workload_loader import IListPodsFallback
from robusta_krr.core.integrations.prometheus import ClusterNotSpecifiedException
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.exceptions import CriticalRunnerException
from robusta_krr.core.models.objects import K8sWorkload
from robusta_krr.core.models.result import ResourceAllocations, ResourceScan, ResourceType, Result, StrategyData
from robusta_krr.utils.intro import load_intro_message
from robusta_krr.utils.progress_bar import ProgressBar
from robusta_krr.utils.version import get_version, load_latest_version


logger = logging.getLogger("krr")


def custom_print(*objects, rich: bool = True, force: bool = False) -> None:
    """
    A wrapper around `rich.print` that prints only if `settings.quiet` is False.
    """
    print_func = settings.logging_console.print if rich else print
    if not settings.quiet or force:
        print_func(*objects)  # type: ignore


class Runner:
    def __init__(self) -> None:
        self.strategy = settings.create_strategy()

        self.errors: list[dict] = []

        # This executor will be running calculations for recommendations
        self.executor = ThreadPoolExecutor(settings.max_workers)

    @staticmethod
    def __parse_version_string(version: str) -> tuple[int, ...]:
        version_trimmed = version.replace("-dev", "").replace("v", "")
        return tuple(map(int, version_trimmed.split(".")))

    def __check_newer_version_available(self, current_version: str, latest_version: str) -> bool:
        try:
            current_version_parsed = self.__parse_version_string(current_version)
            latest_version_parsed = self.__parse_version_string(latest_version)

            if current_version_parsed < latest_version_parsed:
                return True
        except Exception:
            logger.debug("An error occurred while checking for a new version", exc_info=True)
            return False

    async def _greet(self) -> None:
        if settings.quiet:
            return

        current_version = get_version()
        intro_message, latest_version = await asyncio.gather(load_intro_message(), load_latest_version())

        custom_print(intro_message)
        custom_print(f"\nRunning Robusta's KRR (Kubernetes Resource Recommender) {current_version}")
        custom_print(f"Using strategy: {self.strategy}")
        custom_print(f"Using formatter: {settings.format}")
        if latest_version is not None and self.__check_newer_version_available(current_version, latest_version):
            custom_print(f"[yellow bold]A newer version of KRR is available: {latest_version}[/yellow bold]")
        custom_print("")

    def _process_result(self, result: Result) -> None:
        result.errors = self.errors

        Formatter = settings.Formatter
        formatted = result.format(Formatter)
        rich = getattr(Formatter, "__rich_console__", False)

        custom_print(formatted, rich=rich, force=True)

        if settings.file_output or settings.slack_output:
            if settings.file_output:
                file_name = settings.file_output
            elif settings.slack_output:
                file_name = settings.slack_output
            with open(file_name, "w") as target_file:
                console = Console(file=target_file, width=settings.width)
                console.print(formatted)
            if settings.slack_output:
                client = WebClient(os.environ["SLACK_BOT_TOKEN"])
                warnings.filterwarnings("ignore", category=UserWarning)
                client.files_upload(
                    channels=f"#{settings.slack_output}",
                    title="KRR Report",
                    file=f"./{file_name}",
                    initial_comment=f'Kubernetes Resource Report for {(" ".join(settings.namespaces))}',
                )
                os.remove(file_name)

    def __get_resource_minimal(self, resource: ResourceType) -> float:
        if resource == ResourceType.CPU:
            return 1 / 1000 * settings.cpu_min_value
        elif resource == ResourceType.Memory:
            return 1024**2 * settings.memory_min_value
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

    async def _calculate_object_recommendations(self, object: K8sWorkload) -> Optional[RunResult]:
        prometheus = self.connector.get_prometheus(object.cluster)

        if prometheus is None:
            return None

        cluster_loader = self.connector.get_workload_loader(object.cluster)

        object.pods = await prometheus.load_pods(object, self.strategy.settings.history_timedelta)
        if object.pods == [] and isinstance(cluster_loader, IListPodsFallback):
            # Fallback to IListPodsFallback if Prometheus did not return any pods
            # IListPodsFallback is implemented by the Kubernetes API connector
            object.pods = await cluster_loader.load_pods(object)

            # NOTE: Kubernetes API returned pods, but Prometheus did not
            # This might happen with fast executing jobs
            if object.pods != []:
                object.add_warning("NoPrometheusPods")
                logger.warning(
                    f"Was not able to load any pods for {object} from Prometheus. "
                    "Loaded pods from Kubernetes API instead."
                )

        metrics = await prometheus.gather_data(
            object,
            self.strategy,
            self.strategy.settings.history_timedelta,
            step=self.strategy.settings.timeframe_timedelta,
        )

        # NOTE: We run this in a threadpool as the strategy calculation might be CPU intensive
        # But keep in mind that numpy calcluations will not block the GIL
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(self.executor, self.strategy.run, metrics, object)

        logger.info(f"Calculated recommendations for {object} (using {len(metrics)} metrics)")
        return self._format_result(result)

    async def _check_cluster(self, cluster: Optional[str]) -> bool:
        try:
            prometheus_loader = self.connector.get_prometheus(cluster)
        except PrometheusNotFound:
            logger.error(
                f"Wasn't able to connect to any Prometheus service" f" for cluster {cluster}"
                if cluster is not None
                else ""
                "\nTry using port-forwarding and/or setting the url manually (using the -p flag.).\n"
                "For more information, see 'Giving the Explicit Prometheus URL' at "
                "https://github.com/robusta-dev/krr?tab=readme-ov-file#usage"
            )
            return False

        try:
            history_range = await prometheus_loader.get_history_range(timedelta(hours=5))
        except ValueError:
            logger.warning(
                f"Was not able to get history range for cluster {cluster}. This is not critical, will try continue."
            )
            self.errors.append(
                {
                    "name": "HistoryRangeError",
                }
            )
            return True  # We can try to continue without history range

        logger.debug(
            f"History range{f' for cluster {cluster}' if cluster else ''}: "
            f"({history_range[0]})-({history_range[1]})"
        )
        enough_data = self.strategy.settings.history_range_enough(history_range)

        if not enough_data:
            logger.warning(f"Not enough history available for cluster {cluster}.")
            try_after = history_range[0] + self.strategy.settings.history_timedelta

            logger.warning(
                "If the cluster is freshly installed, it might take some time for the enough data to be available."
            )
            logger.warning(
                f"Enough data is estimated to be available after {try_after}, "
                "but will try to calculate recommendations anyway."
            )
            self.errors.append(
                {
                    "name": "NotEnoughHistoryAvailable",
                    "retry_after": try_after,
                }
            )

        return True

    async def _gather_object_allocations(self, k8s_object: K8sWorkload) -> Optional[ResourceScan]:
        try:
            recommendation = await self._calculate_object_recommendations(k8s_object)

            self.__progressbar.progress()

            if recommendation is None:
                return None

            return ResourceScan.calculate(
                k8s_object,
                ResourceAllocations(
                    requests={resource: recommendation[resource].request for resource in ResourceType},
                    limits={resource: recommendation[resource].limit for resource in ResourceType},
                    info={resource: recommendation[resource].info for resource in ResourceType},
                ),
            )
        except Exception as e:
            logger.error(f"Failed to gather allocations for {k8s_object}")
            logger.exception(e)
            return None
    
    async def _collect_result(self) -> Result:
        clusters = await self.connector.list_clusters()
        if clusters is None:
            logger.info("Can not list clusters, single cluster mode.")
        else:
            logger.info(f"Clusters available: {', '.join(clusters)}")

        if clusters and len(clusters) > 1 and settings.prometheus_url:
            # this can only happen for multi-cluster querying a single centeralized prometheus
            # In this scenario we dont yet support determining
            # which metrics belong to which cluster so the reccomendation can be incorrect
            raise ClusterNotSpecifiedException(
                f"Cannot scan multiple clusters for this prometheus, "
                f"Rerun with the flag `-c <cluster>` where <cluster> is one of {clusters}"
            )

        logger.info(f'Using clusters: {clusters if clusters is not None else "inner cluster"}')

        # This is for code clarity. All functions take str | None as cluster parameter
        if clusters is None:
            clusters = [None]

        checks = await asyncio.gather(*[self._check_cluster(cluster) for cluster in clusters])
        clusters = [cluster for cluster, check in zip(clusters, checks) if check]

        if clusters == []:
            raise CriticalRunnerException("No clusters available to scan.")

        workload_loaders = {cluster: self.connector.try_get_workload_loader(cluster) for cluster in clusters}

        # NOTE: we filter out None values as they are clusters that we could not connect to
        workload_loaders = {cluster: loader for cluster, loader in workload_loaders.items() if loader is not None}

        if workload_loaders == {}:
            raise CriticalRunnerException("Could not connect to any cluster.")

        with ProgressBar(title="Calculating Recommendation") as self.__progressbar:
            # We gather all workloads from all clusters in parallel (asyncio.gather)
            # Then we chain all workloads together (itertools.chain)
            workloads = list(
                itertools.chain(
                    *await asyncio.gather(*[loader.list_workloads() for loader in workload_loaders.values()])
                )
            )
            # Then we gather all recommendations for all workloads in parallel (asyncio.gather)
            scans = await asyncio.gather(*[self._gather_object_allocations(k8s_object) for k8s_object in workloads])
            # NOTE: Previously we were streaming workloads to
            # calculate recommendations as soon as they were available (not waiting for all workloads to be loaded),
            # but it gave minor performance improvements (most of the time was spent on calculating recommendations)
            # So we decided to do those two steps sequentially to simplify the code

        successful_scans = [scan for scan in scans if scan is not None]

        if len(scans) == 0:
            logger.warning("Current filters resulted in no objects available to scan.")
            logger.warning("Try to change the filters or check if there is anything available.")
            if settings.namespaces == "*":
                logger.warning(
                    "Note that you are using the '*' namespace filter, which by default excludes kube-system."
                )
            raise CriticalRunnerException("No objects available to scan.")
        elif len(successful_scans) == 0:
            raise CriticalRunnerException("No successful scans were made. Check the logs for more information.")

        return Result(
            scans=successful_scans,
            description=self.strategy.description,
            strategy=StrategyData(
                name=str(self.strategy).lower(),
                settings=self.strategy.settings.dict(),
            ),
        )

    async def run(self) -> int:
        """Run the Runner. The return value is the exit code of the program."""
        await self._greet()

        try:
            # eks has a lower step limit than other types of prometheus, it will throw an error
            step_count = self.strategy.settings.history_duration * 60 / self.strategy.settings.timeframe_duration
            if settings.eks_managed_prom and step_count > 11000:
                min_step = self.strategy.settings.history_duration * 60 / 10000
                logger.warning(
                    f"The timeframe duration provided is insufficient and will be overridden with {min_step}. "
                    f"Kindly adjust --timeframe_duration to a value equal to or greater than {min_step}."
                )
                self.strategy.settings.timeframe_duration = min_step

            self.connector = settings.create_cluster_loader()

            result = await self._collect_result()
            logger.info("Result collected, displaying...")
            self._process_result(result)
        except (ClusterNotSpecifiedException, CriticalRunnerException) as e:
            logger.critical(e)
            return 1  # Exit with error
        except Exception:
            logger.exception("An unexpected error occurred")
            return 1  # Exit with error
        else:
            return 0  # Exit with success
