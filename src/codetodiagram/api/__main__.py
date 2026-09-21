"""Run the API with ``python -m codetodiagram.api``."""

from __future__ import annotations

import uvicorn


def main() -> None:
    """Start uvicorn on localhost:8000."""
    uvicorn.run("codetodiagram.api.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
