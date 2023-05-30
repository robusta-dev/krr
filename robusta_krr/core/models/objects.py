import pydantic as pd

from robusta_krr.core.models.allocations import ResourceAllocations


class K8sObjectData(pd.BaseModel):
    cluster: str
    name: str
    container: str
    pods: list[str]
    namespace: str
    kind: str
    allocations: ResourceAllocations
    deleted_pods_count: int = 0

    def __str__(self) -> str:
        return f"{self.kind} {self.namespace}/{self.name}/{self.container}"

    def __hash__(self) -> int:
        return hash(str(self))

    @property
    def current_pods_count(self) -> int:
        return self.pods_count - self.deleted_pods_count

    @property
    def pods_count(self) -> int:
        return len(self.pods)
