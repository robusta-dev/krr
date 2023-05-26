from typing import Callable, TypeVar, Any

_T = TypeVar("_T")


def display_name_property(*, suffix: str) -> Callable[[type[_T]], type[_T]]:
    """Add a decorator factory to add __display_name__ property to the class.

    It is a utility function for BaseStrategy.
    It makes a __display_name__ property for the class, that uses the name of the class.
    By default, it will remove the suffix from the name of the class.
    For example, if the name of the class is 'MyStrategy', the __display_name__ property will be 'My'.
    If the name of the class is 'Foo', the __display_name__ property will be 'Foo', because it does not end with 'Strategy'.

    If you then override the __display_name__ property, it will be used instead of the default one.
    """

    def decorator(cls: type[_T]) -> type[_T]:
        class DisplayNameProperty:
            # This is a descriptor that returns the name of the class.
            # It is used to generate the __display_name__ property.
            def __get__(self, instance: Any, owner: type[_T]) -> str:
                if owner.__name__.lower().endswith(suffix.lower()):
                    return owner.__name__[: -len(suffix)]

                return owner.__name__

        cls.__display_name__ = DisplayNameProperty()  # type: ignore
        return cls

    return decorator
