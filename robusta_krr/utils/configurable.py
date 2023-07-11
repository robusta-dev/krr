import abc
from inspect import getframeinfo, stack
from typing import Literal, Union

from rich.console import Console

from robusta_krr.core.models.config import Config


class Configurable(abc.ABC):
    """
    A class that can be configured with a Config object.
    Opens the possibility to use custom logging methods, that can be configured with the Config object.

    Also makes a `console` attribute available, which is a rich console.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.console: Console = self.config.console  # type: ignore

    @property
    def debug_active(self) -> bool:
        return self.config.verbose and not self.config.quiet

    @property
    def echo_active(self) -> bool:
        return not self.config.quiet

    @staticmethod
    def __add_prefix(text: str, prefix: str, /, no_prefix: bool) -> str:
        return f"{prefix} {text}" if not no_prefix else text

    def print_result(self, content: str, rich: bool = True) -> None:
        """
        Prints the result in a console. The result is always put in stdout.
        """
        if rich:
            result_console = Console()
            result_console.print(content, overflow="ignore")
        else:
            print(content)

    def echo(
        self, message: str = "", *, no_prefix: bool = False, type: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    ) -> None:
        """
        Echoes a message to the user.
        If quiet mode is enabled, the message will not be echoed
        """

        color = {"INFO": "green", "WARNING": "yellow", "ERROR": "red"}[type]

        if self.echo_active:
            self.console.print(
                self.__add_prefix(message, f"[bold {color}][{type}][/bold {color}]", no_prefix=no_prefix)
            )

    def debug(self, message: str = "") -> None:
        """
        Echoes a message to the user if verbose mode is enabled
        """

        if self.debug_active:
            caller = getframeinfo(stack()[1][0])
            self.console.print(
                self.__add_prefix(
                    message + f"\t\t({caller.filename}:{caller.lineno})",
                    "[bold green][DEBUG][/bold green]",
                    no_prefix=False,
                )
            )

    def debug_exception(self) -> None:
        """
        Echoes the exception traceback to the user if verbose mode is enabled
        """

        if self.debug_active:
            self.console.print_exception()

    def info(self, message: str = "") -> None:
        """
        Echoes an info message to the user
        """

        self.echo(message, type="INFO")

    def warning(self, message: str = "") -> None:
        """
        Echoes a warning message to the user
        """

        self.echo(message, type="WARNING")

    def error(self, message: Union[str, Exception] = "") -> None:
        """
        Echoes an error message to the user
        """

        self.echo(str(message), type="ERROR")
