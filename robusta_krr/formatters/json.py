"""JSON output formatter."""

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.result import Result


@formatters.register()
def json(result: Result) -> str:
    """Format the result as JSON."""
    return result.json(indent=2)
