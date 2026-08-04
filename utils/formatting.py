"""Shared display formatting helpers."""


def format_hours_minutes(seconds: float) -> str:
    """Format a duration in seconds as 'Xh Ym' (e.g. 378h 35m)."""
    total = int(seconds)
    return f"{total // 3600}h {(total % 3600) // 60}m"
