import asyncio
import logging
import math
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Union, List
from datetime import timedelta, datetime
from prometrix import PrometheusNotFound
from rich.console import Console
from slack_sdk import WebClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from urllib.parse import urlparse
import requests
import json
import traceback
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

        self._send_result(settings.publish_scan_url, settings.start_time, settings.scan_id, settings.named_sinks, result)
        formatted = result.format(Formatter)
        rich = getattr(Formatter, "__rich_console__", False)

        custom_print(formatted, rich=rich, force=True)

        if settings.file_output_dynamic or settings.file_output or settings.slack_output or settings.azureblob_output:
            if settings.file_output_dynamic:
                current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
                file_name = f"krr-{current_datetime}.{settings.format}"
                logger.info(f"Writing output to file: {file_name}")
            elif settings.file_output:
                file_name = settings.file_output
            elif settings.slack_output:
                file_name = settings.slack_output
            elif settings.azureblob_output:
                current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
                file_name = f"krr-{current_datetime}.{settings.format}"
                logger.info(f"Writing output to file: {file_name}")

            with open(file_name, "w") as target_file:
                # don't use rich when writing a csv or html to avoid line wrapping etc
                if settings.format in ("csv", "csv-raw", "html", "json", "yaml"):
                    target_file.write(formatted)
                else:
                    console = Console(file=target_file, width=settings.width)
                    console.print(formatted)

            if settings.azureblob_output:
                self._upload_to_azure_blob(file_name, settings.azureblob_output)   
                if settings.teams_webhook:
                    storage_account, container = self._extract_storage_info_from_sas(settings.azureblob_output)
                    self._notify_teams(settings.teams_webhook, storage_account, container)  
                os.remove(file_name)

            if settings.slack_output:
                client = WebClient(os.environ["SLACK_BOT_TOKEN"])
                warnings.filterwarnings("ignore", category=UserWarning)
                
                # Upload file without specifying channel
                result = client.files_upload_v2(
                    title="KRR Report",
                    file_uploads=[{"file": f"./{file_name}", "filename": file_name, "title": "KRR Report"}],
                )
                file_permalink = result["file"]["permalink"]
                
                # Post message with file link to channel
                slack_title = settings.slack_title if settings.slack_title else f'Kubernetes Resource Report for {(" ".join(settings.namespaces))}'
                client.chat_postMessage(
                    channel=settings.slack_output,
                    text=f'{slack_title}\n{file_permalink}'
                )
                
                os.remove(file_name)

    def _upload_to_azure_blob(self, file_name: str, base_sas_url: str):
        try:
            logger.info(f"Uploading {file_name} to Azure Blob Storage")

            with open(file_name, "rb") as file:
                file_data = file.read()

            headers = {
                "Content-Type": "application/octet-stream",
                "x-ms-blob-type": "BlockBlob",
            }

            if file_name.endswith(".csv"):
                headers["Content-Type"] = "text/csv"
            elif file_name.endswith(".json"):
                headers["Content-Type"] = "application/json"
            elif file_name.endswith(".yaml"):
                headers["Content-Type"] = "application/x-yaml"
            elif file_name.endswith(".html"):
                headers["Content-Type"] = "text/html"

            base_url = base_sas_url.rstrip('/')
            url_part, query_part = base_url.split('?', 1)
            full_sas_url = f"{url_part}/{file_name}?{query_part}"

            response = requests.put(full_sas_url, headers=headers, data=file_data)

            if response.status_code == 201:
                logger.info(f"Successfully uploaded {file_name} to Azure Blob Storage")
            else:
                logger.error(f"Failed to upload {file_name} to Azure Blob Storage. Status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
        except Exception as e:
            logger.error(f"An error occurred while uploading {file_name} to Azure Blob Storage: {e}", exc_info=True)

    def _notify_teams(self, webhook_url: str, storage_account: str, container: str):
        """Send notification to Teams with configurable webhook URL."""
        try:
            azure_portal_url = self._build_azure_portal_url(storage_account, container)
            
            adaptive_card = {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "content": {
                            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                            "type": "AdaptiveCard",
                            "version": "1.2",
                            "body": [
                                {
                                    "type": "TextBlock",
                                    "text": "📊 KRR Report Generated",
                                    "weight": "Bolder",
                                    "size": "Medium",
                                    "color": "Good"
                                },
                                {
                                    "type": "TextBlock",
                                    "text": f"Kubernetes Resource Report for {(' '.join(settings.namespaces))} has been generated and uploaded to Azure Blob Storage.",
                                    "wrap": True,
                                    "spacing": "Medium"
                                },
                                {
                                    "type": "FactSet",
                                    "facts": [
                                        {
                                            "title": "Namespaces:",
                                            "value": ' '.join(settings.namespaces)
                                        },
                                        {
                                            "title": "Format:",
                                            "value": settings.format
                                        },
                                        {
                                            "title": "Storage Account:",
                                            "value": storage_account
                                        },
                                        {
                                            "title": "Container:",
                                            "value": container
                                        },
                                        {
                                            "title": "Generated:",
                                            "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        }
                                    ]
                                }
                            ],
                            "actions": [
                                {
                                    "type": "Action.OpenUrl",
                                    "title": "View in Azure Storage",
                                    "url": azure_portal_url
                                }
                            ]
                        }
                    }
                ]
            }
            
            response = requests.post(webhook_url, json=adaptive_card)
            if response.status_code == 202:
                logger.info("Successfully notified Microsoft Teams about the report generation.")
            else:
                logger.error(f"Failed to notify Microsoft Teams. Status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
        except Exception as e:
            logger.error(f"Error sending Teams notification: {e}", exc_info=True)

    def _extract_storage_info_from_sas(self, sas_url: str) -> tuple[str, str]:
        """
        Extracts the storage account name and container name from the SAS URL.
        """
        try:
            parsed = urlparse(sas_url)
            storage_account = parsed.hostname.split('.')[0]  # Extract the storage account name from the hostname
            container = parsed.path.strip('/').split('/')[0]  # Extract the first part of the path as the container name

            return storage_account, container
        except Exception as e:
            logger.error(f"Failed to extract storage info from SAS URL: {e}")
            raise ValueError("Invalid SAS URL format. Please provide a valid Azure Blob Storage SAS URL.") from e
    
    def _build_azure_portal_url(self, storage_account: str, container: str) -> str:
        """
        Builds the Azure portal URL to view the specified storage account and container.
        """

        if not settings.azure_subscription_id or not settings.azure_resource_group:
            # Return a generic Azure portal link if specific info is missing
            logger.warning("Azure subscription ID or resource group not provided. Azure portal link will not be specific.")
        return f"https://portal.azure.com/#view/Microsoft_Azure_Storage/ContainerMenuBlade/~/overview/storageAccountId/%2Fsubscriptions%2F{settings.azure_subscription_id}%2FresourceGroups%2F{settings.azure_resource_group}%2Fproviders%2FMicrosoft.Storage%2FstorageAccounts%2F{storage_account}/path/{container}"

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
            publish_error(f"Could not load kubernetes configuration: {e}")
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
            publish_error(traceback.format_exc())
            return 1  # Exit with error
        except Exception:
            logger.exception("An unexpected error occurred")
            publish_error(traceback.format_exc())
            return 1  # Exit with error
        else:
            return 0  # Exit with success

    def _send_result(self, url: str, start_time: datetime, scan_id: str,named_sinks: Optional[List[str]], result: Result):
        result_dict = json.loads(result.json(indent=2))
        _send_scan_payload(url, scan_id, start_time, result_dict, named_sinks, is_error=False)

def publish_input_error(url: str, scan_id: str, start_time: str, error: str, named_sinks: Optional[List[str]]):
    _send_scan_payload(url, scan_id, start_time, error, named_sinks, is_error=True)

def publish_error(error: str):
    _send_scan_payload(settings.publish_scan_url, settings.scan_id, settings.start_time, error, settings.named_sinks, is_error=True)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True
)
def _post_scan_request(url: str, headers: dict, payload: dict, scan_id: str, is_error: bool):
    logger_msg = "Sending error scan" if is_error else "Sending scan"
    logger.info(f"{logger_msg} for scan_id={scan_id} to url={url}")
    response = requests.post(url, headers=headers, json=payload)
    logger.info(f"scan_id={scan_id} | Status code: {response.status_code}")
    logger.info(f"scan_id={scan_id} | Response body: {response.text}")
    return response


def _send_scan_payload(
    url: str,
    scan_id: str,
    start_time: Union[str, datetime],
    result_data: Union[str, dict],
    named_sinks: Optional[List[str]],
    is_error: bool = False
):
    if not url or not scan_id or not start_time:
        logger.debug(f"Missing required parameters: url={bool(url)}, scan_id={bool(scan_id)}, start_time={bool(start_time)}")
        return

    logger.debug(f"Preparing to send scan payload. scan_id={scan_id}, to sink {named_sinks}, is_error={is_error}")

    headers = {"Content-Type": "application/json"}

    if isinstance(start_time, datetime):
        logger.debug(f"Converting datetime to ISO format for scan_id={scan_id}")
        start_time = start_time.isoformat()

    action_request = {
        "action_name": "process_scan",
        "action_params": {
            "result": result_data,
            "scan_type": "krr",
            "scan_id": scan_id,
            "start_time": start_time,
        }
    }
    if named_sinks:
        action_request["sinks"] = named_sinks

    try:
        _post_scan_request(url, headers, action_request, scan_id, is_error)
    except requests.exceptions.RequestException as e:
        logger.error(f"scan_id={scan_id} | All retry attempts failed due to RequestException: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"scan_id={scan_id} | Unexpected error after retries: {e}", exc_info=True)