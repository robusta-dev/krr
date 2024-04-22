import asyncio
from collections import defaultdict
import logging
from typing import Any, Iterable

from kubernetes.client.models import V1Container, V1Job, V1PodList  # type: ignore

from robusta_krr.core.models.objects import K8sWorkload, PodData

from .base import BaseKindLoader

logger = logging.getLogger("krr")


class CronJobLoader(BaseKindLoader):
    kind = "CronJob"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self._jobs: dict[str, list[V1Job]] = {}
        self._jobs_loading_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def all_namespaces_request(self, label_selector: str) -> Any:
        return self.batch.list_cron_job_for_all_namespaces(label_selector=label_selector, watch=False)

    def namespaced_request(self, namespace: str, label_selector: str) -> Any:
        return self.batch.list_namespaced_cron_job(namespace=namespace, label_selector=label_selector, watch=False)

    async def extract_containers(self, item: Any) -> Iterable[V1Container]:
        return item.spec.job_template.spec.template.spec.containers

    async def list_pods(self, object: K8sWorkload) -> list[PodData]:
        loop = asyncio.get_running_loop()

        namespace_jobs = await self._list_jobs(object.namespace)
        ownered_jobs_uids = [
            job.metadata.uid
            for job in namespace_jobs
            if any(
                owner.kind == "CronJob" and owner.uid == object._api_resource.metadata.uid
                for owner in job.metadata.owner_references or []
            )
        ]
        selector = f"batch.kubernetes.io/controller-uid in ({','.join(ownered_jobs_uids)})"

        ret: V1PodList = await loop.run_in_executor(
            self.executor,
            lambda: self.core.list_namespaced_pod(
                namespace=object._api_resource.metadata.namespace, label_selector=selector
            ),
        )

        return [PodData(name=pod.metadata.name, deleted=False) for pod in ret.items]

    async def _list_jobs(self, namespace: str) -> list[V1Job]:
        if namespace not in self._jobs:
            loop = asyncio.get_running_loop()

            async with self._jobs_loading_locks[namespace]:
                logging.debug(f"Loading jobs for cronjobs in {namespace}")
                ret = await loop.run_in_executor(
                    self.executor,
                    lambda: self.batch.list_namespaced_job(namespace=namespace),
                )
                self._jobs[namespace] = ret.items

        return self._jobs[namespace]
