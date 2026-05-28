"""Agent-specific exceptions raised by Tasks during their execution."""
from __future__ import annotations


class AgentTaskCancelled(InterruptedError):
    """Raised inside ``Task.process`` to signal cooperative cancellation.

    The Task base class installs SIGTERM/SIGINT handlers that raise this exception, giving
    the task a chance to release resources (close files, rollback transactions...) before
    the worker is hard-killed.
    """
