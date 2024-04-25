import logging
from collections import defaultdict
import itertools
import asyncio
from typing import Literal, Union

from robusta_krr.core.models.objects import K8sWorkload, KindLiteral, PodData

from .base import BaseKindLoader

logger = logging.getLogger("krr")

SubownerLiteral = Literal["ReplicaSet", "ReplicationController", "Job"]


class DoubleParentLoader(BaseKindLoader):
    kinds = ["Deployment", "Rollout", "DeploymentConfig", "CronJob"]

    kind_subowner_map: dict[KindLiteral, SubownerLiteral] = {
        "Deployment": "ReplicaSet",
        "Rollout": "ReplicaSet",
        "DeploymentConfig": "ReplicationController",
        "CronJob": "Job",
    }

    async def list_workloads(self, namespaces: Union[list[str], Literal["*"]]) -> list[K8sWorkload]:
        return list(
            itertools.chain(
                *await asyncio.gather(
                    *[
                        self.list_workloads_by_subowner(namespaces, subowner)
                        for subowner in set(self.kind_subowner_map.values())
                    ]
                )
            )
        )

    async def list_workloads_by_subowner(
        self, namespaces: Union[list[str], Literal["*"]], subowner_kind: SubownerLiteral
    ) -> list[K8sWorkload]:
        kinds = [kind for kind in self.kinds_to_scan if self.kind_subowner_map[kind] == subowner_kind]

        if kinds == []:
            return []

        logger.debug(f"Listing {', '.join(kinds)}")
        # NOTE: kube-system is excluded if we scan all namespaces
        namespace_selector = (
            ('namespace=~"' + "|".join(namespaces) + '"') if namespaces != "*" else 'namespace!="kube-system"'
        )

        metric_name = f"kube_{subowner_kind.lower()}_owner"
        subowner_label = subowner_kind.lower() if subowner_kind != "Job" else "job_name"

        # Replica is for ReplicaSet and/or ReplicationController
        subowners = await self.connector.loader.query(
            f"""
                count by (namespace, owner_name, {subowner_label}, owner_kind) (
                    {metric_name} {{
                        {namespace_selector},
                        owner_kind=~"{'|'.join(kinds)}"
                        {self.cluster_selector}
                    }}
                )
            """
        )
        # groupBy: (namespace, owner_name, owner_kind) => [replicaset,...]
        replicas_by_owner = defaultdict(list)
        for subowner in subowners:
            metric = subowner["metric"]
            key = metric["namespace"], metric["owner_name"], metric["owner_kind"]
            replicas_by_owner[key].append(metric[subowner_label])

        return list(
            itertools.chain(
                *await asyncio.gather(
                    *[
                        self._list_pods_of_subowner(
                            namespace,
                            name,
                            kind,
                            subowner_kind,
                            subowners,
                        )
                        for (namespace, name, kind), subowners in replicas_by_owner.items()
                    ]
                )
            )
        )

    async def _list_pods_of_subowner(
        self, namespace: str, name: str, kind: str, subowner_kind: str, subowner_names: list[str]
    ) -> list[K8sWorkload]:
        pods = await self.connector.loader.query(
            f"""
                count by (namespace, owner_name, owner_kind, pod) (
                    kube_pod_owner{{
                        namespace="{namespace}",
                        owner_name=~"{'|'.join(subowner_names)}",
                        owner_kind="{subowner_kind}"
                        {self.cluster_selector}
                    }}
                )
            """
        )
        if pods is None or len(pods) == 0:
            return []

        pod_names = [pod["metric"]["pod"] for pod in pods]
        containers = await self._list_containers_in_pods(pod_names)

        return [
            K8sWorkload(
                cluster=self.connector.cluster,
                namespace=namespace,
                name=name,
                kind=kind,
                container=container_name,
                allocations=await self._parse_allocation(namespace, pod_names, container_name),  # find
                pods=[PodData(name=pod_name, deleted=False) for pod_name in pod_names],  # list pods
            )
            for container_name in containers
        ]
