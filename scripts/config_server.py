#!/usr/bin/env python3
"""Launch the robot assistant configuration service."""

from __future__ import annotations

import argparse

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Bind address for the service.")
    parser.add_argument("--port", type=int, default=8080, help="Port to expose.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (only for local development).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    uvicorn.run(
        "robot_assistant.service.config_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
