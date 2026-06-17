"""CLI entrypoint for local operations and container health checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from customer360.config import load_settings
from customer360.logging import configure_logging
from customer360.monitoring.readiness import ProductionReadinessChecker


def healthcheck() -> int:
    """Validate that configuration can load and the package imports correctly."""
    settings = load_settings()
    print(f"Customer 360 healthcheck passed for environment={settings.environment}")
    return 0


def readiness(
    *,
    config_path: Path | None = None,
    environment: str | None = None,
    strict: bool = False,
    json_output: bool = False,
) -> int:
    """Run production readiness checks and return a deployable exit code."""
    settings = load_settings(config_path, environment=environment)
    report = ProductionReadinessChecker(settings).run()
    if json_output:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(
            "Customer 360 readiness "
            f"environment={report.environment} "
            f"failures={report.failure_count} warnings={report.warning_count}"
        )
        for finding in report.findings:
            prefix = f"[{finding.severity}] {finding.category}.{finding.check_name}"
            print(f"{prefix}: {finding.message}")
            if finding.remediation:
                print(f"  remediation: {finding.remediation}")

    if report.failed or (strict and report.warning_count):
        return 1
    return 0


def main() -> int:
    """Parse CLI commands."""
    configure_logging()
    parser = argparse.ArgumentParser(prog="customer360")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("healthcheck", help="Validate local package and config wiring.")
    readiness_parser = subparsers.add_parser(
        "readiness",
        help="Run production-hardening readiness checks.",
    )
    readiness_parser.add_argument(
        "--config-path",
        type=Path,
        default=None,
        help="Optional config YAML path. Defaults to CUSTOMER360_CONFIG_PATH or CUSTOMER360_ENV.",
    )
    readiness_parser.add_argument(
        "--environment",
        default=None,
        help="Expected environment name, such as dev, test, or prod.",
    )
    readiness_parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when warnings are present.",
    )
    readiness_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON.",
    )
    args = parser.parse_args()

    if args.command == "healthcheck":
        return healthcheck()
    if args.command == "readiness":
        return readiness(
            config_path=args.config_path,
            environment=args.environment,
            strict=args.strict,
            json_output=args.json_output,
        )
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
