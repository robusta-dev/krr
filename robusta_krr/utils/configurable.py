from robusta_krr.core.config import Config
import typer


class Configurable:
    """
    A class that can be configured with a Config object.
    Opens the possibility to use echo and debug methods
    """

    def __init__(self, config: Config) -> None:
        self.config = config

    def echo(self, message: str) -> None:
        """
        Echoes a message to the user.
        If quiet mode is enabled, the message will not be echoed
        """

        if not self.config.quiet:
            typer.echo(message)

    def debug(self, message: str) -> None:
        """
        Echoes a message to the user if verbose mode is enabled
        """

        if self.config.verbose:
            typer.echo(message)
