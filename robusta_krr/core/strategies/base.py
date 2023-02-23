import abc
import pydantic as pd
from typing import Generic, TypeVar
from robusta_krr.core.result import ResourceType, ObjectData


class StrategySettings(pd.BaseModel):
    history_duration: float = pd.Field(
        24 * 7 * 2, ge=1, description="The duration of the history data to use (in hours)."
    )


_StrategySettings = TypeVar("_StrategySettings", bound=StrategySettings)
HistoryData = dict[str, list[float]]


class BaseStrategy(abc.ABC, Generic[_StrategySettings]):
    __name__: str

    def __init__(self, settings: _StrategySettings):
        self.settings = settings

    def run(self, history_data: HistoryData, object_data: ObjectData, resource_type: ResourceType) -> float:
        raise NotImplementedError
