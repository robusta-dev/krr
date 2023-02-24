import pydantic as pd

from robusta_krr.core.strategies import (
    BaseStrategy,
    HistoryData,
    K8sObjectData,
    ResourceRecommendation,
    ResourceType,
    StrategySettings,
)


class SimpleStrategySettings(StrategySettings):
    request_percentile: float = pd.Field(
        0.9, gt=0, le=1, description="The percentile to use for the request recommendation."
    )
    limit_percentile: float = pd.Field(
        0.99, gt=0, le=1, description="The percentile to use for the limit recommendation."
    )


class SimpleStrategy(BaseStrategy[SimpleStrategySettings]):
    __display_name__ = "simple"

    def run(
        self, history_data: HistoryData, object_data: K8sObjectData, resource_type: ResourceType
    ) -> ResourceRecommendation:
        points_flatten = [point for points in history_data.values() for point in points]
        return ResourceRecommendation(
            request=self._calculate_percentile(points_flatten, self.settings.request_percentile),
            limit=self._calculate_percentile(points_flatten, self.settings.limit_percentile),
        )

    def _calculate_percentile(self, data: list[float], percentile: float) -> float:
        data = sorted(data)
        return data[int(len(data) * percentile)]
