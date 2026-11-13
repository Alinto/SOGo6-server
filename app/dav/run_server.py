"""Gunicorn target of the DAV server: ``gunicorn -c app/gunicorn.conf.py app.dav.run_server:app``."""

import logging

from flask import Flask

from app.dav.build_app import build_app

app: Flask = build_app()

# Send Flask logs through gunicorn's handlers.
gunicorn_logger: logging.Logger = logging.getLogger("gunicorn.error")
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)
