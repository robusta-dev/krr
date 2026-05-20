"""Pretty-print output formatter."""

from pprint import pformat

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.result import Result


@formatters.register()
def pprint(result: Result) -> str:
    """Format the result as a pretty-printed string."""
    return pformat(result.dict())
