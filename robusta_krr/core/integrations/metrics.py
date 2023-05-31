import asyncio
import itertools
from typing import Optional, List, Dict
from collections import defaultdict

from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData, PodData
from robusta_krr.core.models.result import ResourceAllocations, ResourceType, RecommendationValue
from robusta_krr.utils.configurable import Configurable
from .prometheus.loader import MetricsLoader

class PrometheusLoader(Configurable):    
    def __init__(self, config: Config):
        super().__init__(config)
        self.metrics_loader = MetricsLoader(config)

    async def list_clusters(self) -> Optional[list[str]]:
        self.debug("Working in Prometheus-based workload discovery mode. Only support a single cluster")
        return None

    async def list_scannable_objects(self, clusters: Optional[list[str]]) -> list[K8sObjectData]:
        """List all scannable objects from Prometheus
        In this workload discovery mode, clusters are not supported.

        Returns:
            A list of scannable objects.
        """
        self.info(f"Listing scannable objects from Prometheus")
        self.debug(f"Namespaces: {self.config.namespaces}")
        try:
            objects_tuple = await asyncio.gather(
                self._list_deployments(),
            )
        except Exception as e:
            self.error(f"Error trying to list pods from Prometheus: {e}")
            self.debug_exception()
            return []
    
        objects = itertools.chain(*objects_tuple)
        if self.config.namespaces == "*":
            # NOTE: We are not scanning kube-system namespace by default
            result = [obj for obj in objects if obj.namespace != "kube-system"]
        else:
            result = [obj for obj in objects if obj.namespace in self.config.namespaces]

        namespaces = {obj.namespace for obj in result}
        self.info(f"Found {len(result)} objects across {len(namespaces)} namespaces from Prometheus({self.config.prometheus_url})")

        return result
    
    async def __parse_allocation(self, namespace: str, pod_selector: str, container_name: str) -> ResourceAllocations:
        limits = await self.metrics_loader.loader.query("avg by(resource) (kube_pod_container_resource_limits{"
                                               f'namespace="{namespace}", '
                                               f'pod=~"{pod_selector}", '
                                               f'container="{container_name}"'
                                               "})")
        requests = await self.metrics_loader.loader.query("avg by(resource) (kube_pod_container_resource_requests{"
                                               f'namespace="{namespace}", '
                                               f'pod=~"{pod_selector}", '
                                               f'container="{container_name}"'
                                               "})")
        requests_values: Dict[ResourceType, RecommendationValue] = {ResourceType.CPU: None, ResourceType.Memory: None}
        limits_values: Dict[ResourceType, RecommendationValue] = {ResourceType.CPU: None, ResourceType.Memory: None}
        for limit in limits:
            if limit['metric']['resource'] == ResourceType.CPU:
                limits_values[ResourceType.CPU] = float(limit['value'][1])
            elif limit['metric']['resource'] == ResourceType.Memory:
                limits_values[ResourceType.Memory] = float(limit['value'][1])

        for request in requests:
            if request['metric']['resource'] == ResourceType.CPU:
                requests_values[ResourceType.CPU] = float(request['value'][1])
            elif request['metric']['resource'] == ResourceType.Memory:
                requests_values[ResourceType.Memory] = float(request['value'][1])
        return ResourceAllocations(requests=requests_values, limits=limits_values)
        
    
    async def __build_from_owner(self, namespace: str, app_name: str, containers: List[str], pod_names: List[str]) -> List[K8sObjectData]:
        return [
            K8sObjectData(
                cluster="default",
                namespace=namespace,
                name=app_name,
                kind="Deployment",
                container=container_name,
                allocations=await self.__parse_allocation(namespace, "|".join(pod_names), container_name), # find 
                pods=[PodData(name=pod_name, deleted=False) for pod_name in pod_names], # list pods
            )
            for container_name in containers
        ]
        
    async def _list_containers(self, namespace: str, pod_selector: str) -> List[str]:
        containers = await self.metrics_loader.loader.query("count by (container) (kube_pod_container_info{"
                                               f'namespace="{namespace}", '
                                               f'pod=~"{pod_selector}"'
                                               "})")
        return [container['metric']['container'] for container in containers]
    
    async def _list_containers_in_pods(self, app_name: str, pod_owner_kind: str, namespace: str, owner_name: str) -> list[K8sObjectData]:
        if pod_owner_kind == "ReplicaSet":
            # owner_name is ReplicaSet names
            pods = await self.metrics_loader.loader.query("count by (owner_name, replicaset, pod) (kube_pod_owner{"
                                               f'namespace="{namespace}", '
                                               f'owner_name=~"{owner_name}", '
                                               'owner_kind="ReplicaSet"})')
            if pods is None or len(pods) == 0:
                return [] # no container
            # [{'metric': {'owner_name': 'wbjs-algorithm-base-565b645489', 'pod': 'wbjs-algorithm-base-565b645489-jqt4x'}, 'value': [1685529217, '1']}, 
            #  {'metric': {'owner_name': 'wbjs-algorithm-base-565b645489', 'pod': 'wbjs-algorithm-base-565b645489-lj9qg'}, 'value': [1685529217, '1']}]
            pod_names = [pod['metric']['pod'] for pod in pods]
            container_names = await self._list_containers(namespace, "|".join(pod_names))
            return await self.__build_from_owner(namespace, app_name, container_names, pod_names)
        return []

    async def _list_deployments(self) -> list[K8sObjectData]:
        self.debug(f"Listing deployments in namespace({self.config.namespaces}) from Prometheus({self.config.prometheus_url})")
        ns = "|".join(self.config.namespaces)
        replicasets = await self.metrics_loader.loader.query("count by (namespace, owner_name, replicaset) (kube_replicaset_owner{"
                                               f'namespace=~"{ns}", '
                                               'owner_kind="Deployment"})')
        # groupBy: 'ns/owner_name' => [{metadata}...]
        pod_owner_kind = "ReplicaSet"
        replicaset_dict = defaultdict(list)
        for replicaset in replicasets:
            replicaset_dict[replicaset['metric']['namespace'] + "/" + replicaset['metric']['owner_name']].append(replicaset['metric'])
        objects = await asyncio.gather(
            *[
                self._list_containers_in_pods(deployment[0]['owner_name'], pod_owner_kind, deployment[0]['namespace'], "|".join(list(map(lambda metric: metric['replicaset'], deployment))))
                for deployment in replicaset_dict.values()
            ]
        )
        return list(itertools.chain(*objects))
