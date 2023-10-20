from alive_progress import alive_bar

# from robusta_krr.core.models.config import settings


class ProgressBar:
    """
    Progress bar for displaying progress of gathering recommendations.

    Use `ProgressBar` as a context manager to automatically handle the progress bar.
    Use `progress` method to step the progress bar.
    """

    def __init__(self, **kwargs) -> None:
        # self.show_bar = not settings.quiet and not settings.log_to_stderr
        self.show_bar = False  # FIXME: Progress bar is not working good with other logs
        if self.show_bar:
            self.alive_bar = alive_bar(**kwargs, enrich_print=False)

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
