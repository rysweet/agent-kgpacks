#!/usr/bin/env python3
"""Launch Kuzu Explorer for interactive graph visualization.

Kuzu Explorer is a browser-based UI for exploring graph databases.
It runs as a Docker container (kuzudb/explorer) and mounts the local
database directory as a volume.

Usage:
    python bootstrap/scripts/explore.py [--db data/wikigr_1k.db] [--port 8000]

Requirements:
    Docker must be installed and running.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

DOCKER_IMAGE = "kuzudb/explorer:latest"


def _check_docker() -> str:
    """Return the path to docker (or podman), or exit with an error."""
    for cmd in ("docker", "podman"):
        path = shutil.which(cmd)
        if path is not None:
            return path
    print("Error: Neither docker nor podman found in PATH.")
    print("Install Docker: https://docs.docker.com/get-docker/")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch Kuzu Explorer for interactive graph visualization"
    )
    parser.add_argument(
        "--db",
        default="data/wikigr_1k.db",
        help="Path to Kuzu database directory (default: data/wikigr_1k.db)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to serve on (default: 8000)",
    )
    args = parser.parse_args()

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        print("Run the expansion pipeline first to create a database:")
        print("  python bootstrap/quickstart.py")
        sys.exit(1)

    docker = _check_docker()

    # Pull the image if not already present
    print(f"Ensuring {DOCKER_IMAGE} is available...")
    pull_result = subprocess.run(
        [docker, "image", "inspect", DOCKER_IMAGE],
        capture_output=True,
    )
    if pull_result.returncode != 0:
        print(f"Pulling {DOCKER_IMAGE}...")
        subprocess.run([docker, "pull", DOCKER_IMAGE], check=True)

    print(f"Launching Kuzu Explorer on http://localhost:{args.port}")
    print(f"Database: {db_path}")
    print("Press Ctrl+C to stop.")
    print()

    container_name = "wikigr-explorer"

    # Stop any existing container with the same name
    subprocess.run(
        [docker, "rm", "-f", container_name],
        capture_output=True,
    )

    cmd = [
        docker,
        "run",
        "--name",
        container_name,
        "-p",
        f"{args.port}:8000",
        "-v",
        f"{db_path}:/database",
        "-e",
        "MODE=READ_ONLY",
        "--rm",
        DOCKER_IMAGE,
    ]

    # Add Podman-specific flag for volume permissions
    if "podman" in docker:
        cmd.insert(-1, "--userns=keep-id")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nKuzu Explorer stopped.")


if __name__ == "__main__":
    main()
