"""DAV server development entry point: ``poetry run dav``.

Production serves the same application through gunicorn, see ``run_server.py``.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

import os

import click

from app.config.init_config import init_once
from app.dav.build_app import build_app
from app.utils.logger.logger import logger_dav

if TYPE_CHECKING:
    from flask import Flask


@click.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=5001)
@click.option("--debug/--no-debug", default=True)
def main(host: str, port: int, debug: bool) -> None:
    """Start the DAV server on the Werkzeug development server."""
    # The reloader runs this module again in a child process: check the database only once.
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        init_once()
    app: Flask = build_app()
    if debug:
        logger_dav.warning("SOGo DAV server is in debug mode")
    app.run(host=host, port=port, debug=debug)
