"""Shared test output helpers for QuarkSum.

Toggle via pytest --no-reports (default: reports ON).
"""

_ENABLED = True


def set_enabled(flag: bool) -> None:
    global _ENABLED
    _ENABLED = flag


def sci(v: float) -> str:
    """Scientific notation with 6 decimal places."""
    return f"{v:.6e}"


def pct(v: float) -> str:
    """Signed percentage with 4 decimal places."""
    return f"{v:+.4f}%"


def report(title: str, lines: list[str]) -> None:
    """Print a box-formatted report block. Silenced by --no-reports."""
    if not _ENABLED:
        return
    width = max((len(l) for l in lines), default=40) + 4
    width = max(width, len(title) + 6)
    print()
    print(f"  ┌{'─' * (width - 2)}┐")
    print(f"  │ {title:<{width - 4}} │")
    print(f"  ├{'─' * (width - 2)}┤")
    for line in lines:
        print(f"  │ {line:<{width - 4}} │")
    print(f"  └{'─' * (width - 2)}┘")
