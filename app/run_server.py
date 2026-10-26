import logging
from app.build_app import build_app

app = build_app()

# send Flask logs through gunicorn's handlers
gunicorn_logger = logging.getLogger("gunicorn.error")
app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)
