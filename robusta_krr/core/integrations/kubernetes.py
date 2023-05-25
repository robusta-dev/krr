import asyncio
import itertools
from typing import Optional, Union

from kubernetes import client, config  # type: ignore
from kubernetes.client.models import (
    V1Container,
    V1DaemonSet,
    V1DaemonSetList,
    V1Deployment,
    V1DeploymentList,
    V1Job,
    V1JobList,
    V1LabelSelector,
    V1PodList,
    V1StatefulSet,
    V1StatefulSetList,
)

from robusta_krr.core.models.objects import K8sObjectData, PodData
from robusta_krr.core.models.result import ResourceAllocations
from robusta_krr.utils.configurable import Configurable


class ClusterLoader(Configurable):
    def __init__(self, cluster: Optional[str], *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cluster = cluster
        self.api_client = config.new_client_from_config(context=cluster) if cluster is not None else None
        self.apps = client.AppsV1Api(api_client=self.api_client)
        self.batch = client.BatchV1Api(api_client=self.api_client)
        self.core = client.CoreV1Api(api_client=self.api_client)

    async def list_scannable_objects(self) -> list[K8sObjectData]:
        """List all scannable objects.

        Returns:
            A list of scannable objects.
        """

        self.info(f"Listing scannable objects in {self.cluster}")
        self.debug(f"Namespaces: {self.config.namespaces}")
        self.debug(f"Resources: {self.config.resources}")

        try:
            list_fns = []
            if self._should_list_resource("deployments"):
                list_fns.append(self._list_deployments)
            if self._should_list_resource("statefulsets"):
                list_fns.append(self._list_all_statefulsets)
            if self._should_list_resource("daemon_set"):
                list_fns.append(self._list_all_daemon_set)
            if self._should_list_resource("jobs"):
                list_fns.append(self._list_all_jobs)

            objects_tuple = await asyncio.gather(*(fn() for fn in list_fns))
        except Exception as e:
            self.error(f"Error trying to list pods in cluster {self.cluster}: {e}")
            self.debug_exception()
            return []

        objects = list(itertools.chain(*objects_tuple))
        namespaces = {obj.namespace for obj in objects}
        self.info(f"Found {len(objects)} objects across {len(namespaces)} namespaces in {self.cluster}")

        return objects

    def _should_list_resource(self, resource: str):
        if self.config.resources == "*":
            return True
        return resource in self.config.resources

    @staticmethod
    def _get_match_expression_filter(expression) -> str:
        if expression.operator.lower() == "exists":
            return expression.key
        elif expression.operator.lower() == "doesnotexist":
            return f"!{expression.key}"

        values = ",".join(expression.values)
        return f"{expression.key} {expression.operator} ({values})"

    @staticmethod
    def _build_selector_query(selector: V1LabelSelector) -> Union[str, None]:
        label_filters = [f"{label[0]}={label[1]}" for label in selector.match_labels.items()]

        if selector.match_expressions is not None:
            label_filters.extend(
                [ClusterLoader._get_match_expression_filter(expression) for expression in selector.match_expressions]
            )

        return ",".join(label_filters)

    async def __list_pods(self, resource: Union[V1Deployment, V1DaemonSet, V1StatefulSet]) -> list[PodData]:
        selector = self._build_selector_query(resource.spec.selector)
        if selector is None:
            return []

        ret: V1PodList = await asyncio.to_thread(
            self.core.list_namespaced_pod, namespace=resource.metadata.namespace, label_selector=selector
        )
        return [PodData(name=pod.metadata.name, deleted=False) for pod in ret.items]

    async def __build_obj(
        self, item: Union[V1Deployment, V1DaemonSet, V1StatefulSet], container: V1Container
    ) -> K8sObjectData:
        return K8sObjectData(
            cluster=self.cluster,
            namespace=item.metadata.namespace,
            name=item.metadata.name,
            kind=item.__class__.__name__[2:],
            container=container.name,
            allocations=ResourceAllocations.from_container(container),
            pods=await self.__list_pods(item),
        )

    async def _list_resources(self, all_namespaces_fn, namespaced_fn):
        resources = []
        if self.config.namespaces == "*":
            ret: V1DeploymentList = await asyncio.to_thread(all_namespaces_fn, watch=False)
            for item in ret.items:
                resources.append(item)
        else:
            for namespace in self.config.namespaces:
                ret: V1DeploymentList = await asyncio.to_thread(namespaced_fn, namespace, watch=False)
                for item in ret.items:
                    resources.append(item)
        return resources

    async def _list_deployments(self) -> list[K8sObjectData]:
        self.debug(f"Listing deployments in {self.cluster}")
        deployments: list[V1Deployment] = await self._list_resources(
            self.apps.list_deployment_for_all_namespaces,
            self.apps.list_namespaced_deployment
        )
        self.debug(f"Found {len(deployments)} deployments in {self.cluster}")

        return await asyncio.gather(
            *[
                self.__build_obj(item, container)
                for item in deployments
                for container in item.spec.template.spec.containers
            ]
        )

    async def _list_all_statefulsets(self) -> list[K8sObjectData]:
        self.debug(f"Listing statefulsets in {self.cluster}")
        statefulsets: list[V1StatefulSet] = await self._list_resources(
            self.apps.list_stateful_set_for_all_namespaces,
            self.apps.list_namespaced_stateful_set
        )
        self.debug(f"Found {len(statefulsets)} statefulsets in {self.cluster}")

        return await asyncio.gather(
            *[
                self.__build_obj(item, container)
                for item in statefulsets
                for container in item.spec.template.spec.containers
            ]
        )

    async def _list_all_daemon_set(self) -> list[K8sObjectData]:
        self.debug(f"Listing daemonsets in {self.cluster}")
        ret: V1DaemonSetList = await asyncio.to_thread(self.apps.list_daemon_set_for_all_namespaces, watch=False)
        self.debug(f"Found {len(ret.items)} daemonsets in {self.cluster}")

        return await asyncio.gather(
            *[
                self.__build_obj(item, container)
                for item in ret.items
                for container in item.spec.template.spec.containers
            ]
        )

    async def _list_all_jobs(self) -> list[K8sObjectData]:
        self.debug(f"Listing jobs in {self.cluster}")
        jobs: list[V1Job] = await self._list_resources(
            self.batch.list_job_for_all_namespaces,
            self.batch.list_namespaced_job
        )
        self.debug(f"Found {len(jobs)} jobs in {self.cluster}")

        return await asyncio.gather(
            *[
                self.__build_obj(item, container)
                for item in jobs
                for container in item.spec.template.spec.containers
            ]
        )

    async def _list_pods(self) -> list[K8sObjectData]:
        """For future use, not supported yet."""

        self.debug(f"Listing pods in {self.cluster}")
        ret: V1PodList = await asyncio.to_thread(self.apps.list_pod_for_all_namespaces, watch=False)
        self.debug(f"Found {len(ret.items)} pods in {self.cluster}")

        return await asyncio.gather(
            *[self.__build_obj(item, container) for item in ret.items for container in item.spec.containers]
        )


class KubernetesLoader(Configurable):
    async def list_clusters(self) -> Optional[list[str]]:
        """List all clusters.

        Returns:
            A list of clusters.
        """

        if self.config.inside_cluster:
            self.debug("Working inside the cluster")
            return None

        contexts, current_context = await asyncio.to_thread(config.list_kube_config_contexts)

        self.debug(f"Found {len(contexts)} clusters: {', '.join([context['name'] for context in contexts])}")
        self.debug(f"Current cluster: {current_context['name']}")

        self.debug(f"Configured clusters: {self.config.clusters}")

        # None, empty means current cluster
        if not self.config.clusters:
            return [current_context["name"]]

        # * means all clusters
        if self.config.clusters == "*":
            return [context["name"] for context in contexts]

        return [context["name"] for context in contexts if context["name"] in self.config.clusters]

    async def list_scannable_objects(self, clusters: Optional[list[str]]) -> list[K8sObjectData]:
        """List all scannable objects.

        Returns:
            A list of scannable objects.
        """

        if clusters is None:
            cluster_loaders = [ClusterLoader(cluster=None, config=self.config)]
        else:
            cluster_loaders = [ClusterLoader(cluster=cluster, config=self.config) for cluster in clusters]

        objects = await asyncio.gather(*[cluster_loader.list_scannable_objects() for cluster_loader in cluster_loaders])
        return list(itertools.chain(*objects))
