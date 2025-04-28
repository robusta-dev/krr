import asyncio
import logging
import math
import os
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Union
from datetime import timedelta, datetime
from prometrix import PrometheusNotFound
from rich.console import Console
from slack_sdk import WebClient

from robusta_krr.core.abstract.strategies import ResourceRecommendation, RunResult
from robusta_krr.core.integrations.kubernetes import KubernetesLoader
from robusta_krr.core.integrations.prometheus import ClusterNotSpecifiedException, PrometheusMetricsLoader
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.result import ResourceAllocations, ResourceScan, ResourceType, Result, StrategyData
from robusta_krr.utils.intro import load_intro_message
from robusta_krr.utils.progress_bar import ProgressBar
from robusta_krr.utils.version import get_version, load_latest_version
from robusta_krr.utils.patch import create_monkey_patches

logger = logging.getLogger("krr")


def custom_print(*objects, rich: bool = True, force: bool = False) -> None:
    """
    A wrapper around `rich.print` that prints only if `settings.quiet` is False.
    """
    print_func = settings.logging_console.print if rich else print
    if not settings.quiet or force:
        print_func(*objects)  # type: ignore


class CriticalRunnerException(Exception): ...


class Runner:
    EXPECTED_EXCEPTIONS = (KeyboardInterrupt, PrometheusNotFound)

    def __init__(self) -> None:
        self._k8s_loader = KubernetesLoader()
        self._metrics_service_loaders: dict[Optional[str], Union[PrometheusMetricsLoader, Exception]] = {}
        self._metrics_service_loaders_error_logged: set[Exception] = set()
        self._strategy = settings.create_strategy()

        self.errors: list[dict] = []

        # This executor will be running calculations for recommendations
        self._executor = ThreadPoolExecutor(settings.max_workers)

    def _get_prometheus_loader(self, cluster: Optional[str]) -> Optional[PrometheusMetricsLoader]:
        if cluster not in self._metrics_service_loaders:
            try:
                self._metrics_service_loaders[cluster] = PrometheusMetricsLoader(cluster=cluster)
            except Exception as e:
                self._metrics_service_loaders[cluster] = e

        result = self._metrics_service_loaders[cluster]
        if isinstance(result, self.EXPECTED_EXCEPTIONS):
            if result not in self._metrics_service_loaders_error_logged:
                self._metrics_service_loaders_error_logged.add(result)
                logger.error(str(result))
            return None
        elif isinstance(result, Exception):
            raise result

        return result

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
        custom_print(f"Using strategy: {self._strategy}")
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

        if settings.file_output_dynamic or settings.file_output or settings.slack_output:
            if settings.file_output_dynamic:
                current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
                file_name = f"krr-{current_datetime}.{settings.format}"
                logger.info(f"Writing output to file: {file_name}")
            elif settings.file_output:
                file_name = settings.file_output
            elif settings.slack_output:
                file_name = settings.slack_output

            with open(file_name, "w") as target_file:
                # don't use rich when writing a csv or html to avoid line wrapping etc
                if settings.format in ("csv", "csv-raw", "html", "json", "yaml"):
                    target_file.write(formatted)
                else:
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

    async def _calculate_object_recommendations(self, object: K8sObjectData) -> Optional[RunResult]:
        try:
            prometheus_loader = self._get_prometheus_loader(object.cluster)

            if prometheus_loader is None:
                return None

            object.pods = await prometheus_loader.load_pods(object, self._strategy.settings.history_timedelta)
            if object.pods == []:
                # Fallback to Kubernetes API
                object.pods = await self._k8s_loader.load_pods(object)

                # NOTE: Kubernetes API returned pods, but Prometheus did not
                # This might happen with fast executing jobs
                if object.pods != []:
                    object.add_warning("NoPrometheusPods")
                    logger.warning(
                        f"Was not able to load any pods for {object} from Prometheus. "
                        "Loaded pods from Kubernetes API instead."
                    )

            metrics = await prometheus_loader.gather_data(
                object,
                self._strategy,
                self._strategy.settings.history_timedelta,
                step=self._strategy.settings.timeframe_timedelta,
            )

            # NOTE: We run this in a threadpool as the strategy calculation might be CPU intensive
            # But keep in mind that numpy calcluations will not block the GIL
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(self._executor, self._strategy.run, metrics, object)

            logger.info(f"Calculated recommendations for {object} (using {len(metrics)} metrics)")
            return self._format_result(result)
        except Exception as e:
            logger.error(f"An error occurred while calculating recommendations for {object}: {e}")
            return None

    async def _check_data_availability(self, cluster: Optional[str]) -> None:
        prometheus_loader = self._get_prometheus_loader(cluster)
        if prometheus_loader is None:
            return

        try:
            history_range = await prometheus_loader.get_history_range(timedelta(hours=5))
        except ValueError:
            logger.info(
                f"Unable to check how much historical data is available on cluster {cluster}. Will assume it is sufficient and calculate recommendations anyway. (You can usually ignore this. Not all Prometheus compatible metric stores support checking history settings.)"
            )
            self.errors.append(
                {
                    "name": "HistoryRangeError",
                }
            )
            return

        logger.debug(f"History range for {cluster}: {history_range}")
        enough_data = self._strategy.settings.history_range_enough(history_range)

        if not enough_data:
            logger.warning(f"Not enough history available for cluster {cluster}.")
            try_after = history_range[0] + self._strategy.settings.history_timedelta

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

    async def _gather_object_allocations(self, k8s_object: K8sObjectData) -> Optional[ResourceScan]:
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

    async def _collect_result(self) -> Result:
        clusters = await self._k8s_loader.list_clusters()
        if clusters and len(clusters) > 1 and settings.prometheus_url:
            # this can only happen for multi-cluster querying a single centeralized prometheus
            # In this scenario we dont yet support determining
            # which metrics belong to which cluster so the reccomendation can be incorrect
            raise ClusterNotSpecifiedException(
                f"Cannot scan multiple clusters for this prometheus, "
                f"Rerun with the flag `-c <cluster>` where <cluster> is one of {clusters}"
            )

        logger.info(f'Using clusters: {clusters if clusters is not None else "inner cluster"}')

        if clusters is None:
            await self._check_data_availability(None)
        else:
            await asyncio.gather(*[self._check_data_availability(cluster) for cluster in clusters])

        with ProgressBar(title="Calculating Recommendation") as self.__progressbar:
            workloads = await self._k8s_loader.list_scannable_objects(clusters)
            if not clusters or len(clusters) == 1:
                cluster_name = clusters[0] if clusters else None # its none if krr is running inside cluster
                prometheus_loader = self._get_prometheus_loader(cluster_name)
                cluster_summary = await prometheus_loader.get_cluster_summary()
            else:
                cluster_summary = {}
            scans = await asyncio.gather(*[self._gather_object_allocations(k8s_object) for k8s_object in workloads])

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
            description=f"[b]{self._strategy.display_name.title()} Strategy[/b]\n\n{self._strategy.description}",
            strategy=StrategyData(
                name=str(self._strategy).lower(),
                settings=self._strategy.settings.dict(),
            ),
            clusterSummary=cluster_summary
        )

    async def run(self) -> int:
        """Run the Runner. The return value is the exit code of the program."""
        await self._greet()
        try:
            settings.load_kubeconfig()
        except Exception as e:
            logger.error(f"Could not load kubernetes configuration: {e}")
            logger.error("Try to explicitly set --context and/or --kubeconfig flags.")
            return 1  # Exit with error

        try:
            create_monkey_patches()
            # eks has a lower step limit than other types of prometheus, it will throw an error
            step_count = self._strategy.settings.history_duration * 60 / self._strategy.settings.timeframe_duration
            if settings.eks_managed_prom and step_count > 11000:
                min_step = self._strategy.settings.history_duration * 60 / 10000
                logger.warning(
                    f"The timeframe duration provided is insufficient and will be overridden with {min_step}. "
                    f"Kindly adjust --timeframe_duration to a value equal to or greater than {min_step}."
                )
                self._strategy.settings.timeframe_duration = min_step

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
