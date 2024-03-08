class dict_to_object:
    def __init__(self, dictionary):
        for key, value in dictionary.items():
            if isinstance(value, dict):
                value = dict_to_object(value)  # Convert inner dict
            if isinstance(value, list):
                value = [dict_to_object(item) if isinstance(item, dict) else item for item in value]
            self.__dict__[key] = value

    def __getattr__(self, name):
        return self.__dict__.get(name)

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __str__(self):
        return str(self.__dict__)

    def __repr__(self):
        return repr(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def get(self, key, default=None):
        return self.__dict__.get(key, default)

    def items(self):
        return self.__dict__.items()
