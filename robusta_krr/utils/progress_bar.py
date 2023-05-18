from robusta_krr.utils.configurable import Configurable
from alive_progress import alive_bar
from robusta_krr.core.models.config import Config
import sys

class ProgressBar(Configurable):
    def __init__(self, config: Config, **kwargs) -> None:
        super().__init__(config)
        self.show_bar = self.echo_active
        if self.show_bar:
            self.alive_bar = alive_bar(**kwargs)
            self.bar = self.alive_bar.__enter__()

    def progress(self):
        if self.show_bar:
            self.bar()
     
    def close_bar(self):
        if self.show_bar:
            self.alive_bar.__exit__(*sys.exc_info())