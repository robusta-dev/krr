import pydantic as pd
from .base import BaseStrategy, StrategySettings, HistoryData, ObjectData, ResourceType


class SimpleStrategySettings(StrategySettings):
    percentile: float = pd.Field(0.95, gt=0, le=1, description="The percentile to use for the recommendation.")


class SimpleStrategy(BaseStrategy[StrategySettings]):
    __name__ = "simple"

    def run(self, history_data: HistoryData, object_data: ObjectData, resource_type: ResourceType) -> float:
        return self._calculate_percentile(
            [point for points in history_data.values() for point in points], self.settings.percentile
        )

    def _calculate_percentile(self, data: list[float], percentile: float) -> float:
        data = sorted(data)
        return data[int(len(data) * percentile)]
