"""Calendar module tasks. Importing each Task here triggers its ``@agent_task``
decorator so it is collected by the registry. Add a line per new task."""
from app.module.calendar.tasks.ExportIcsTask import ExportIcsTask  # noqa: F401
