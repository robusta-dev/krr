import typer
from rich import print

from robusta_krr.core.config import Config


class Configurable:
    """
    A class that can be configured with a Config object.
    Opens the possibility to use echo and debug methods
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    @staticmethod
    def __add_prefix(text: str, prefix: str, /, no_prefix: bool) -> str:
        return f"{prefix} {text}" if not no_prefix else text

    def echo(self, message: str = "", *, no_prefix: bool = False) -> None:
        """
        Echoes a message to the user.
        If quiet mode is enabled, the message will not be echoed
        """

        if not self.config.quiet and self.config.verbose:
            print(self.__add_prefix(message, "[bold green][INFO][/bold green]", no_prefix=no_prefix))

    def debug(self, message: str = "") -> None:
        """
        Echoes a message to the user if verbose mode is enabled
        """

        if self.config.verbose:
            print(self.__add_prefix(message, "[bold green][DEBUG][/bold green]", no_prefix=False))
