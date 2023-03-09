from rich.console import Console

from typing import Literal

from robusta_krr.core.models.config import Config


console = Console()


class Configurable:
    """
    A class that can be configured with a Config object.
    Opens the possibility to use echo and debug methods
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.console = console

    @staticmethod
    def __add_prefix(text: str, prefix: str, /, no_prefix: bool) -> str:
        return f"{prefix} {text}" if not no_prefix else text

    def echo(
        self, message: str = "", *, no_prefix: bool = False, type: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    ) -> None:
        """
        Echoes a message to the user.
        If quiet mode is enabled, the message will not be echoed
        """

        color = {"INFO": "green", "WARNING": "yellow", "ERROR": "red"}[type]

        if not self.config.quiet:
            self.console.print(
                self.__add_prefix(message, f"[bold {color}][{type}][/bold {color}]", no_prefix=no_prefix)
            )

    def debug(self, message: str = "") -> None:
        """
        Echoes a message to the user if verbose mode is enabled
        """

        if self.config.verbose and not self.config.quiet:
            self.console.print(self.__add_prefix(message, "[bold green][DEBUG][/bold green]", no_prefix=False))

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

    def error(self, message: str = "") -> None:
        """
        Echoes an error message to the user
        """

        self.echo(message, type="ERROR")
