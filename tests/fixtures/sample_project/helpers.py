"""Shared helpers called from the route and ``__main__``."""

import requests

from users import display_name


def greet(name: object) -> str:
    """Format a greeting; used by both entry points."""
    return format_message(display_name(name))


def format_message(text: str) -> str:
    """Wrap ``text`` in a greeting prefix."""
    return f"Hello {text}"


def fetch_remote() -> str:
    """Unresolvable external call: ``requests.get``."""
    response = requests.get("https://example.com")
    return parse_status(response)


def parse_status(response: object) -> str:
    """Read a status-like attribute from the response."""
    code = getattr(response, "status_code", 0)
    return str(code)
