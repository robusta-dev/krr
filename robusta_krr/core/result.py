import pydantic as pd

from robusta_krr.core.formatters import BaseFormatter, get_formatter, FormatType


class Result(pd.BaseModel):
    def format(self, formatter: BaseFormatter | FormatType) -> str:
        """Format the result.

        Args:
            formatter: The formatter to use.

        Returns:
            The formatted result.
        """
        if isinstance(formatter, str):
            formatter = get_formatter(formatter)

        return formatter.format(self)
