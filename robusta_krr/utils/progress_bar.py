"""Progress bar utility for displaying recommendation gathering progress."""

from alive_progress import alive_bar

# from robusta_krr.core.models.config import settings


class ProgressBar:
    """
    Progress bar for displaying progress of gathering recommendations.

    Use `ProgressBar` as a context manager to automatically handle the progress bar.
    Use `progress` method to step the progress bar.
    """

    def __init__(self, **kwargs) -> None:
        """Initialize the ProgressBar with the given alive_bar arguments."""
        # self.show_bar = not settings.quiet and not settings.log_to_stderr
        self.show_bar = False  # FIXME: Progress bar is not working good with other logs
        if self.show_bar:
            self.alive_bar = alive_bar(**kwargs, enrich_print=False)

    def __enter__(self):
        """Enter the context manager and start the progress bar."""
        if self.show_bar:
            self.bar = self.alive_bar.__enter__()
        return self

    def progress(self):
        """Advance the progress bar by one step."""
        if self.show_bar:
            self.bar()

    def __exit__(self, *args):
        """Exit the context manager and stop the progress bar."""
        if self.show_bar:
            self.alive_bar.__exit__(*args)
