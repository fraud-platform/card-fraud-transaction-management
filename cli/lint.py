from cli._runner import run


def main() -> None:
    """Run linting."""
    import sys

    sys.exit(run(["uv", "run", "ruff", "check", "."]))


def format() -> None:
    """Run code formatting."""
    import sys

    sys.exit(run(["uv", "run", "ruff", "format", "."]))
