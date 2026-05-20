"""Dictionary subclass that allows attribute-style access to keys."""


class ObjectLikeDict:
    """A dictionary that supports attribute-style access to its keys."""
    def __init__(self, dictionary):
        """Initialize from a dictionary, converting nested dicts."""
        for key, value in dictionary.items():
            if isinstance(value, dict):
                value = ObjectLikeDict(value)  # Convert inner dict
            if isinstance(value, list):
                value = [ObjectLikeDict(item) if isinstance(item, dict) else item for item in value]
            self.__dict__[key] = value

    def __getattr__(self, name):
        """Return the value for the given attribute name, or None."""
        return self.__dict__.get(name)

    def __setattr__(self, name, value):
        """Set the value for the given attribute name."""
        self.__dict__[name] = value

    def __str__(self):
        """Return a string representation of the dictionary."""
        return str(self.__dict__)

    def __repr__(self):
        """Return a repr string of the underlying dictionary."""
        return repr(self.__dict__)

    def __len__(self):
        """Return the number of items in the dictionary."""
        return len(self.__dict__)

    def get(self, key, default=None):
        """Return the value for key, or a default value if not found."""
        return self.__dict__.get(key, default)

    def items(self):
        """Return a view of the dictionary's items."""
        return self.__dict__.items()
