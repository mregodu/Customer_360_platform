"""CLI entrypoint for local operations and container health checks."""

from __future__ import annotations

import argparse

from customer360.config import load_settings
from customer360.logging import configure_logging


def healthcheck() -> int:
    """Validate that configuration can load and the package imports correctly."""
    settings = load_settings()
    print(f"Customer 360 healthcheck passed for environment={settings.environment}")
    return 0


def main() -> int:
    """Parse CLI commands."""
    configure_logging()
    parser = argparse.ArgumentParser(prog="customer360")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("healthcheck", help="Validate local package and config wiring.")
    args = parser.parse_args()

    if args.command == "healthcheck":
        return healthcheck()
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
