import pydantic as pd


class K8sObjectData(pd.BaseModel):
    name: str
    kind: str
    namespace: str

    def __str__(self) -> str:
        return f"{self.kind}/{self.namespace}/{self.name}"

    def __hash__(self) -> int:
        return hash(str(self))
