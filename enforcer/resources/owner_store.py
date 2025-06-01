import logging
import threading
import time
from typing import Dict, Any, Optional, List

from enforcer.env_vars import REPLICA_SET_CLEANUP_INTERVAL, REPLICA_SET_DELETION_WAIT
from enforcer.metrics import rs_owners_size
from enforcer.model import PodOwner, RsOwner
from enforcer.resources.kubernetes_resource_loader import KubernetesResourceLoader


class OwnerStore:

    def __init__(self):
        self.rs_owners: Dict[str, RsOwner] = {}
        self._rs_owners_lock = threading.Lock()
        self._owners_loaded = threading.Event()
        self._loading_in_progress = threading.Lock()
        self.cleanup_interval = REPLICA_SET_CLEANUP_INTERVAL
        self._stop_event = threading.Event()
        self._cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
        self._cleanup_thread.start()

    def _rs_key(self, rs_name: str, namespace: str) -> str:
        return f"{namespace}/{rs_name}"

    def finalize_owner_initialization(self):
        """Initialize rs_owners on-demand, thread-safe, only once."""
        if self._owners_loaded.is_set():
            return  # Already loaded
            
        # Try to acquire the loading lock without blocking
        if not self._loading_in_progress.acquire(blocking=False):
            # Another thread is loading, just return
            return
            
        try:
            if self._owners_loaded.is_set():
                return
                
            replica_sets_owners: List[RsOwner] = KubernetesResourceLoader.load_replicasets()
            loaded_owners: Dict[str, RsOwner] = {}
            for owner in replica_sets_owners:
                loaded_owners[self._rs_key(owner.rs_name, owner.namespace)] = owner
            
            with self._rs_owners_lock:
                self.rs_owners.update(loaded_owners)
                rs_owners_size.set(len(self.rs_owners))
            
            self._owners_loaded.set()
            logging.info(f"Loaded {len(loaded_owners)} ReplicaSet owners")
            
        except Exception:
            logging.exception(f"Failed to load ReplicaSet owners")
        finally:
            self._loading_in_progress.release()

    @staticmethod
    def get_pod_name(metadata: Dict[str, Any]) -> str:
        # if the pod's name is randomized, the name is under generateName
        return metadata.get("name") or metadata.get("generateName")

    def get_pod_owner(self, pod: Dict[str, Any]) -> Optional[PodOwner]:
        metadata = pod.get("metadata", {})
        owner_references = metadata.get("ownerReferences", [])
        namespace: str = metadata.get("namespace")

        try:
            if not owner_references:  # pod has no owner, standalone pod. Return the pod
                return PodOwner(
                    kind="Pod", namespace=namespace, name=self.get_pod_name(pod)
                )

            # get only owners with controller == true
            controllers = [owner for owner in owner_references if owner.get("controller", False)]
            if controllers:
                if len(controllers) > 1:
                    logging.warning(f"Multiple controllers found for {pod}")

                controller = controllers[0]
                controller_kind: str = controller.get("kind")
                if controller_kind == "ReplicaSet":
                    with self._rs_owners_lock:
                        rs_owner = self.rs_owners.get(self._rs_key(controller.get("name"), namespace), None)
                        return PodOwner(
                            name=rs_owner.owner_name,
                            namespace=rs_owner.namespace,
                            kind=rs_owner.owner_kind,
                        ) if rs_owner else None
                else:  # Pod owner is a k8s workload: Job, StatefulSet, DaemonSet
                    return PodOwner(kind=controller_kind, name=controller.get("name"), namespace=namespace)
        except Exception:
            logging.exception(f"Failed to get pod owner for {pod}")

        return None

    def handle_rs_admission(self, request: Dict[str, Any]):
        logging.debug(f"handle_rs_admission %s", request)
        operation = request.get("operation")
        if operation == "DELETE":
            old_object = request.get("oldObject") or {}  # delete has old object
            metadata = old_object.get("metadata", {})
            rs_name = metadata.get("name")
            namespace = metadata.get("namespace")
            if rs_name and namespace:
                with self._rs_owners_lock:
                    rs_owner = self.rs_owners.get(self._rs_key(rs_name, namespace), None)
                    if rs_owner:
                        rs_owner.deletion_ts = time.time()
        elif operation == "CREATE":
            self._add_rs_owner(request)

    def _add_rs_owner(self, rs_create_request: Dict[str, Any]):
        metadata = rs_create_request.get("object", {}).get("metadata", {})
        owner_references = metadata.get("ownerReferences", [])
        if len(owner_references):
            rs_owner = RsOwner(
                rs_name=metadata.get("name"),
                namespace=metadata.get("namespace"),
                owner_name=owner_references[0].get("name"),
                owner_kind=owner_references[0].get("kind"),
            )
            with self._rs_owners_lock:
                self.rs_owners[self._rs_key(rs_owner.rs_name, rs_owner.namespace)] = rs_owner
        else:
            logging.warning(f"No owner references for {rs_create_request}")


    def _cleanup_deleted_replica_sets(self):
        current_time = time.time()

        with self._rs_owners_lock:
            # Delete rs owners that were deleted more than REPLICA_SET_DELETION_WAIT seconds ago
            keys_to_delete = [
                key for key, rs_owner in self.rs_owners.items()
                if rs_owner.deletion_ts is not None and (current_time - rs_owner.deletion_ts) >= REPLICA_SET_DELETION_WAIT
            ]
            
            for key in keys_to_delete:
                del self.rs_owners[key]

    def _periodic_cleanup(self):
        while not self._stop_event.wait(self.cleanup_interval):
            try:
                self._cleanup_deleted_replica_sets()
                logging.debug("Deleted replicasets cleanup completed")
            except Exception as e:
                logging.exception(f"Failed to cleanup deleted replicasets")

    def get_rs_owners_count(self) -> int:
        with self._rs_owners_lock:
            return len(self.rs_owners)

    def stop(self):
        self._stop_event.set()
        self._cleanup_thread.join()