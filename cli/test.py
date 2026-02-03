from cli._runner import run


def main() -> None:
    """Run tests."""
    import sys

    sys.exit(run(["uv", "run", "pytest"]))


def test_v() -> None:
    """Run tests with verbose output."""
    import sys

    sys.exit(run(["uv", "run", "pytest", "-v"]))


def test_all() -> None:
    """Run all tests including e2e."""
    import sys

    sys.exit(run(["uv", "run", "pytest", "--all"]))


def test_smoke() -> None:
    """Run smoke tests only."""
    import sys

    sys.exit(run(["uv", "run", "pytest", "-m", "smoke"]))


def test_e2e() -> None:
    """Run e2e integration tests only."""
    import sys

    sys.exit(run(["uv", "run", "pytest", "-m", "e2e_integration"]))
