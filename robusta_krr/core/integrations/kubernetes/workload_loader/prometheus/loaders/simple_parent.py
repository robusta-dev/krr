import asyncio
from collections import defaultdict
import logging
from typing import Literal, Union

from robusta_krr.core.models.objects import K8sWorkload, PodData

from .base import BaseKindLoader

logger = logging.getLogger("krr")


class SimpleParentLoader(BaseKindLoader):
    kinds = ["DaemonSet", "StatefulSet", "Job"]

    async def list_workloads(self, namespaces: Union[list[str], Literal["*"]]) -> list[K8sWorkload]:
        if self.kinds_to_scan == []:
            return []

        logger.debug(f"Listing {', '.join(self.kinds_to_scan)}")
        namespace_selector = (
            ('namespace=~"' + "|".join(namespaces) + '"') if namespaces != "*" else 'namespace!="kube-system"'
        )

        results = await self.prometheus.loader.query(
            f"""
                count by (namespace, owner_name, owner_kind, pod) (
                    kube_pod_owner{{
                        {namespace_selector},
                        owner_kind=~"{'|'.join(self.kinds_to_scan)}"
                        {self.cluster_selector}
                    }}
                )
            """
        )
        if results is None or len(results) == 0:
            return []

        # groupBy: (namespace, owner_name, owner_kind) => [pod, ... ]
        workloads: defaultdict[tuple[str, str, str], list[str]] = defaultdict(list)
        for result in results:
            metric = result["metric"]
            key = metric["namespace"], metric["owner_name"], metric["owner_kind"]
            workloads[key].append(metric["pod"])

        # NOTE: We do not show jobs that are a part of a cronjob, so we filter them out
        job_workloads = [name for (_, name, kind) in workloads if kind == "Job"]
        if job_workloads != []:
            cronjobs = await self.prometheus.loader.query(
                f"""
                    count by (namespace, job_name) (
                        kube_job_owner{{
                            {namespace_selector},
                            owner_kind="CronJob"
                            {self.cluster_selector}
                        }}
                    )
                """
            )
            for cronjob in cronjobs:
                metric = cronjob["metric"]
                key = (metric["namespace"], metric["job_name"], "Job")
                if key in workloads:
                    del workloads[key]

        workloads_containers = dict(
            zip(
                workloads.keys(),
                await asyncio.gather(*[self._list_containers_in_pods(pods) for pods in workloads.values()]),
            )
        )

        return [
            K8sWorkload(
                cluster=self.prometheus.cluster,
                namespace=namespace,
                name=name,
                kind=kind,
                container=container,
                allocations=await self._parse_allocation(namespace, pod_names, container),  # find
                pods=[PodData(name=pod_name, deleted=False) for pod_name in pod_names],  # list pods
            )
            for (namespace, name, kind), pod_names in workloads.items()
            for container in workloads_containers[namespace, name, kind]
        ]
