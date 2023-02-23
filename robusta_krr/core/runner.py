from robusta_krr.core.result import Result
from robusta_krr.utils.configurable import Configurable
from robusta_krr.utils.version import get_version
from robusta_krr.core.strategies import (
    BaseStrategy,
    StrategySettings,
    HistoryData,
    ObjectData,
    ResourceType,
    get_strategy_from_name,
)


class Runner(Configurable):
    def _greet(self) -> None:
        self.echo(f"Running Robusta's KRR (Kubernetes Resource Recommender) {get_version()}")

    def _process_result(self, result: Result) -> None:
        formatted = result.format(self.config.format)
        self.echo(formatted)

    def _collect_result(self) -> Result:
        data: HistoryData = {}
        strategy = self.config.create_strategy()

        strategy.run(data, {}, ResourceType.cpu)

        return Result()

    def run(self) -> None:
        self._greet()
        result = self._collect_result()
        self._process_result(result)
