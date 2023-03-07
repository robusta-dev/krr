import pydantic as pd


class K8sObjectData(pd.BaseModel):
    cluster: str
    name: str
    container: str
    namespace: str
    kind: str | None

    def __str__(self) -> str:
        return f"{self.kind} {self.namespace}/{self.name}/{self.container}"

    def __hash__(self) -> int:
        return hash(str(self))
