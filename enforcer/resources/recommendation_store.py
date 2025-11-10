import logging
import threading
from typing import Dict, Optional, Tuple

from enforcer.dal.supabase_dal import SupabaseDal
from enforcer.env_vars import SCAN_RELOAD_INTERVAL
from enforcer.model import WorkloadRecommendation, ContainerRecommendation


class RecommendationStore:

    def __init__(self, dal: SupabaseDal):
        self.dal = dal
        self.recommendations: Dict[str, WorkloadRecommendation] = {}
        self.scan_id: Optional[str] = None
        self._recommendations_lock = threading.Lock()
        self._reload_recommendations()

        self.reload_interval = SCAN_RELOAD_INTERVAL
        self._stop_event = threading.Event()
        self._reload_thread = threading.Thread(target=self._periodic_reload, daemon=True)
        self._reload_thread.start()


    def _load_recommendations(self, current_stored_scan: Optional[str]) -> Tuple[Optional[str], Optional[Dict[str, WorkloadRecommendation]]]:
        latest_scan_id, latest_scan = self.dal.get_latest_krr_scan(current_stored_scan)

        if not latest_scan:
            return None, None

        # group workload containers recommendations, into WorkloadRecommendation object
        scan_recommendations: Dict[str, WorkloadRecommendation] = {}
        for container_recommendation in latest_scan:
            try:
                store_key = self._store_key(
                        name=container_recommendation["name"],
                        namespace=container_recommendation["namespace"],
                        kind=container_recommendation["kind"],
                    )

                recommendation = ContainerRecommendation.build(container_recommendation)
                if recommendation:  # if a valid recommendation was created, connect it to the workload
                    workload_recommendation: WorkloadRecommendation = scan_recommendations.get(store_key, None)
                    if not workload_recommendation:
                        workload_recommendation = WorkloadRecommendation(workload_key=store_key)
                        scan_recommendations[store_key] = workload_recommendation

                    workload_recommendation.add(container_recommendation["container"], recommendation)
            except Exception:
                logging.exception(f"Failed to load container recommendation: {container_recommendation}")

        return latest_scan_id, scan_recommendations

    def _store_key(self, name: str, namespace: str, kind: str) -> str:
        return f"{namespace}/{name}/{kind}"

    def _reload_recommendations(self):
        scan_id, new_recommendations = self._load_recommendations(self.scan_id)
        if new_recommendations is not None:
            with self._recommendations_lock:
                self.recommendations = new_recommendations
                self.scan_id = scan_id
                logging.info("Recommendations reloaded successfully")
                logging.debug("Loaded recommendations: %s", new_recommendations)

    def _periodic_reload(self):
        while not self._stop_event.wait(self.reload_interval):
            try:
                self._reload_recommendations()
            except Exception as e:
                logging.error(f"Failed to reload recommendations: {e}")

    def stop(self):
        self._stop_event.set()
        self._reload_thread.join()

    def get_recommendations(self, name: str, namespace: str, kind: str) -> Optional[WorkloadRecommendation]:
        with self._recommendations_lock:
            return self.recommendations.get(self._store_key(name, namespace, kind))

