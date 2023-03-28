from decimal import Decimal

UNITS = {
    "m": Decimal("1e-3"),
    "Ki": Decimal(1024),
    "Mi": Decimal(1024**2),
    "Gi": Decimal(1024**3),
    "Ti": Decimal(1024**4),
    "Pi": Decimal(1024**5),
    "Ei": Decimal(1024**6),
    "k": Decimal(1e3),
    "M": Decimal(1e6),
    "G": Decimal(1e9),
    "T": Decimal(1e12),
    "P": Decimal(1e15),
    "E": Decimal(1e18),
}


def parse(x: str) -> Decimal:
    """Converts a string to an integer with respect of units."""
    for unit, multiplier in UNITS.items():
        if x.endswith(unit):
            return Decimal(x[: -len(unit)]) * multiplier
    return Decimal(x)


def format(x: Decimal, prescision: int | None = None) -> str:
    """Converts an integer to a string with respect of units."""

    if prescision is not None:
        # Use inly the first prescision digits, starting from the biggest one
        # Example? 123456 -> 123000
        assert prescision >= 0

        exponent: int
        sign, digits, exponent = x.as_tuple()  # type: ignore
        x = Decimal((sign, list(digits[:prescision]) + [0] * (len(digits) - prescision), exponent))

    if x == 0:
        return "0"

    for unit, multiplier in reversed(UNITS.items()):
        if x % multiplier == 0:
            v = int(x / multiplier)
            return f"{v}{unit}"
    return str(x)
