"""Minimal Flask app used as the analyzer fixture."""

from flask import Flask

from helpers import fetch_remote, greet
from users import load_user

app = Flask(__name__)


@app.route("/")
def index() -> str:
    """HTTP entry: greet a user and hit an external HTTP call."""
    user = load_user("1")
    return greet(user) + fetch_remote()


def unused_view() -> str:
    """Not reachable from any entry point."""
    return "noop"


if __name__ == "__main__":
    greet("world")
