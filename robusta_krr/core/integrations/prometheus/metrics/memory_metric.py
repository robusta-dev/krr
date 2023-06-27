from robusta_krr.core.models.allocations import ResourceType
from robusta_krr.core.models.objects import K8sObjectData

from .base_filtered_metric import BaseFilteredMetricLoader
from .base_metric import bind_metric


@bind_metric(ResourceType.Memory)
class MemoryMetricLoader(BaseFilteredMetricLoader):
    def get_query(self, object: K8sObjectData) -> str:
        if object.kind == "Deployment":
            return f"""
                max by (namespace, pod) (
                    label_replace(
                        kube_pod_owner{{owner_kind="ReplicaSet"}}, "replicaset", "$1", "owner_name", "(.*)"
                    ) * on (namespace, replicaset) group_left(owner_name) topk by (namespace, replicaset) (
                        1, max by (namespace, replicaset, owner_name) (
                            kube_replicaset_owner{{owner_kind="Deployment", owner_name="{object.name}"}}
                        )
                    )
                ) * on(namespace, pod) group_right() avg by (namespace, pod, container) (
                    sum by (namespace, pod, container, job, service) (
                        container_memory_working_set_bytes{{namespace="{object.namespace}", container="{object.container}", image!=""}}
                    )
                )
            """
        else:
            return f"""
                max by (namespace, pod) (
                    kube_pod_owner{{owner_kind="{object.kind}", owner_name="{object.name}"}}
                ) * on(namespace, pod) group_right() avg by (namespace, pod, container) (
                    sum by (namespace, pod, container, job, service) (
                        container_memory_working_set_bytes{{namespace="{object.namespace}", container="{object.container}", image!=""}}
                    )
                )
            """
