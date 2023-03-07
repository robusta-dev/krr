from decimal import Decimal

UNITS = {
    "m": 1e-3,
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


def parse(x: str) -> Decimal:
    """Converts a string to an integer with respect of units."""
    for unit, multiplier in UNITS.items():
        if x.endswith(unit):
            return Decimal(x[: -len(unit)]) * Decimal(multiplier)
    return Decimal(x)


def format(x: float | None) -> str | None:
    """Converts an integer to a string with respect of units."""
    if x is None:
        return None

    for unit, multiplier in UNITS.items():
        if Decimal(x) % Decimal(multiplier) == 0:
            return f"{Decimal(x) / Decimal(multiplier)}{unit}"
    return str(x)[:-2]
