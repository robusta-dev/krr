import sys

from rich import print as r_print

from robusta_krr.core.models.config import settings

py_print = print


def print(*objects, rich: bool = True, force: bool = False) -> None:
    """
    A wrapper around `rich.print` that prints only if `settings.quiet` is False.
    """
    print_func = r_print if rich else py_print
    output = sys.stdout if force or not settings.log_to_stderr else sys.stderr

    if not settings.quiet or force:
        print_func(*objects, file=output)  # type: ignore


__all__ = ["print"]
