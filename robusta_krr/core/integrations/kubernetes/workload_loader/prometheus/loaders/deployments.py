import logging
from collections import defaultdict
import itertools
import asyncio
from typing import Literal, Optional, Union

from robusta_krr.core.models.objects import K8sWorkload

from .base import BaseKindLoader

logger = logging.getLogger("krr")


class DeploymentLoader(BaseKindLoader):
    kind = "Deployment"

    async def list_workloads(self, namespaces: Union[list[str], Literal["*"]], label_selector: str) -> list[K8sWorkload]:
        logger.debug(
            f"Listing deployments in namespace({namespaces})"
        )
        ns = "|".join(namespaces)
        replicasets = await self.metrics_loader.loader.query(
            f"""
                count by (namespace, owner_name, replicaset) (
                    kube_replicaset_owner{{
                        namespace=~"{ns}",
                        owner_kind="Deployment",
                    }}
                )
            """
        )
        # groupBy: 'ns/owner_name' => [{metadata}...]
        pod_owner_kind = "ReplicaSet"
        replicaset_dict = defaultdict(list)
        for replicaset in replicasets:
            replicaset_dict[replicaset["metric"]["namespace"] + "/" + replicaset["metric"]["owner_name"]].append(
                replicaset["metric"]
            )
        objects = await asyncio.gather(
            *[
                self._list_containers_in_pods(
                    replicas[0]["owner_name"],
                    pod_owner_kind,
                    replicas[0]["namespace"],
                    "|".join(list(map(lambda metric: metric["replicaset"], replicas))),
                )
                for replicas in replicaset_dict.values()
            ]
        )
        return list(itertools.chain(*objects))
