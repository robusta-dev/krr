import tomllib


def get_version() -> str:
    with open("pyproject.toml", "rb") as file:
        pyproject = tomllib.load(file)
    return pyproject["tool"]["poetry"]["version"]
