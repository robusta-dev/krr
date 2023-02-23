from .base import BaseStrategy, StrategySettings, HistoryData, ObjectData, ResourceType
from .simple import SimpleStrategy, SimpleStrategySettings


def get_strategy_from_name(name: str) -> type[BaseStrategy]:
    """Get a strategy from its name."""

    strategies = {cls.__name__.lower(): cls for cls in BaseStrategy.__subclasses__()}
    if name.lower() in strategies:
        return strategies[name.lower()]

    raise ValueError(f"Unknown strategy name: {name}. Available strategies: {', '.join(strategies)}")


__all__ = [
    "AVAILABLE_STRATEGIES",
    "get_strategy_from_name",
    "BaseStrategy",
    "StrategySettings",
    "HistoryData",
    "ObjectData",
    "ResourceType",
    "SimpleStrategy",
    "SimpleStrategySettings",
]
