from alive_progress import alive_bar

from robusta_krr.core.models.config import Config
from robusta_krr.utils.configurable import Configurable


class ProgressBar(Configurable):
    """
    Progress bar for displaying progress of gathering recommendations.

    Use `ProgressBar` as a context manager to automatically handle the progress bar.
    Use `progress` method to step the progress bar.
    """

    def __init__(self, config: Config, **kwargs) -> None:
        super().__init__(config)
        self.show_bar = self.echo_active
        if self.show_bar:
            self.alive_bar = alive_bar(**kwargs)

    def __enter__(self):
        if self.show_bar:
            self.bar = self.alive_bar.__enter__()
        return self

    def progress(self):
        if self.show_bar:
            self.bar()

    def __exit__(self, *args):
        if self.show_bar:
            self.alive_bar.__exit__(*args)
