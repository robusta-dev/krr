from robusta_krr.core.models.config import settings


def print(*objects, rich: bool = True, force: bool = False) -> None:
    """
    A wrapper around `rich.print` that prints only if `settings.quiet` is False.
    """
    print_func = settings.logging_console.print if rich else print

    if not settings.quiet or force:
        print_func(*objects)  # type: ignore


__all__ = ["print"]
