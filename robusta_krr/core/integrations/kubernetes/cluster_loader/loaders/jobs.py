from typing import Any

from .base import BaseKindLoader


class JobLoader(BaseKindLoader):
    kind = "Job"

    def all_namespaces_request(self, label_selector: str) -> Any:
        return self.batch.list_job_for_all_namespaces(label_selector=label_selector, watch=False)

    def namespaced_request(self, namespace: str, label_selector: str) -> Any:
        return self.batch.list_namespaced_job(namespace=namespace, label_selector=label_selector, watch=False)

    def filter(self, item: Any) -> bool:
        # NOTE: If the job has ownerReference and it is a CronJob,
        # then we should skip it, as it is a part of the CronJob
        return not any(owner.kind == "CronJob" for owner in item.metadata.owner_references or [])
