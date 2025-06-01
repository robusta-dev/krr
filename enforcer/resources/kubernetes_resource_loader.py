import os
import logging
from typing import List

from enforcer.env_vars import DISCOVERY_MAX_BATCHES, DISCOVERY_BATCH_SIZE
from kubernetes import client
from kubernetes.client import V1ReplicaSetList
from kubernetes import config

from enforcer.model import RsOwner

if os.getenv("KUBERNETES_SERVICE_HOST"):
    config.load_incluster_config()
else:
    config.load_kube_config()


class KubernetesResourceLoader:

    @staticmethod
    def load_replicasets() -> List[RsOwner]:
        cluster_rs: List[RsOwner] = []
        continue_ref = None
        for batch_num in range(DISCOVERY_MAX_BATCHES):
            replicasets: V1ReplicaSetList = client.AppsV1Api().list_replica_set_for_all_namespaces(
                limit=DISCOVERY_BATCH_SIZE, _continue=continue_ref
            )

            for replicaset in replicasets.items:
                owner_references = replicaset.metadata.owner_references
                if owner_references:
                    rs_owner = owner_references[0]
                    if len(owner_references) > 1:
                        logging.warning(f"ReplicasSet with multiple owner_references: {owner_references}")
                        controllers = [owner for owner in owner_references if owner.get("controller", False)]
                        if controllers:
                            rs_owner = controllers[0]

                    cluster_rs.append(RsOwner(
                        rs_name=replicaset.metadata.name,
                        namespace=replicaset.metadata.namespace,
                        owner_name=rs_owner.name,
                        owner_kind=rs_owner.kind,
                    ))

            continue_ref = replicasets.metadata._continue
            if not continue_ref:
                break
            
            if batch_num == DISCOVERY_MAX_BATCHES - 1:
                replicas_limit = DISCOVERY_MAX_BATCHES * DISCOVERY_BATCH_SIZE
                logging.warning(f"Reached replicas loading limit: {replicas_limit}.")
        
        return cluster_rs
