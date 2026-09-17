"""User helpers used by the sample app."""


def load_user(user_id: str) -> str:
    """Resolve a user id to a display name."""
    return display_name(user_id)


def display_name(name: object) -> str:
    """Normalize any name-like value."""
    return normalize(name)


def normalize(name: object) -> str:
    """Identity helper so the sample has ~10 functions."""
    return str(name)


def unused_helper() -> None:
    """Dead code; must not appear in the pruned graph."""
    return None
