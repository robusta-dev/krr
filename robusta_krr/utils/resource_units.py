from typing import Literal, Union

UNITS: dict[str, float] = {
    "m": 0.001,
    "Ki": 1024,
    "Mi": 1024**2,
    "Gi": 1024**3,
    "Ti": 1024**4,
    "Pi": 1024**5,
    "Ei": 1024**6,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
    "T": 1e12,
    "P": 1e15,
    "E": 1e18,
}


def parse(x: str, /) -> Union[float, int]:
    """Converts a string to an integer with respect of units."""

    for unit, multiplier in UNITS.items():
        if x.endswith(unit):
            return float(x[: -len(unit)]) * multiplier

    return float(x)


def get_base(x: str, /) -> Literal[1024, 1000]:
    """Returns the base of the unit."""

    for unit, _ in UNITS.items():
        if x.endswith(unit):
            return 1024 if unit in ["Ki", "Mi", "Gi", "Ti", "Pi", "Ei"] else 1000
    return 1000 if "." in x else 1024


def format(x: Union[float, int], /, *, base: Literal[1024, 1000] = 1024) -> str:
    """Converts an integer to a string with respect of units."""

    if x < 1:
        return f"{int(x*1000)}m"
    if x < base:
        return str(x)

    units = ["", "K", "M", "G", "T", "P", "E"]
    binary_units = ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei"]

    x = int(x)
    for i, unit in enumerate(binary_units if base == 1024 else units):
        if x < base ** (i + 1) or i == len(units) - 1 or x / base ** (i + 1) < 10:
            return f"{x/base**i:.0f}{unit}"
    return f"{x/6**i:.0f}{unit}"
