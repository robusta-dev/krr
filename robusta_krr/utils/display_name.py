from typing import Callable, TypeVar

_T = TypeVar("_T")


def add_display_name(*, postfix: str) -> Callable[[type[_T]], type[_T]]:
    """Add a decorator factory to add __display_name__ property to the class."""

    def decorator(cls: type[_T]) -> type[_T]:
        class DisplayNameProperty:
            def __get__(self, instance, owner):
                if owner.__name__.lower().endswith(postfix.lower()):
                    return owner.__name__[: -len(postfix)]

                return owner.__name__

        cls.__display_name__ = DisplayNameProperty()
        return cls

    return decorator
