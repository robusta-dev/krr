from robusta_krr.core.result import Result
from robusta_krr.utils.configurable import Configurable
from robusta_krr.utils.version import get_version


class Runner(Configurable):
    def _greet(self) -> None:
        self.echo(f"Running Robusta's KRR (Kubernetes Resource Recommender) {get_version()}")

    def _process_result(self, result: Result) -> None:
        formatted = result.format(self.config.format)
        self.echo(formatted)

    def _collect_result(self) -> Result:
        return Result()

    def run(self) -> None:
        self._greet()
        result = self._collect_result()
        self._process_result(result)
