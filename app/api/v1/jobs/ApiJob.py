from __future__ import annotations

from flask import g
from flask.typing import ResponseReturnValue
from flask.views import MethodView
from flask_smorest import Blueprint

from app.interface.job.InterfaceApiJob import InterfaceApiJob
from app.utils.logger.logger import logger_api

from .schemas.job import JobResponseSchema, JobResultQueryArgsSchema

blp = Blueprint("Job", __name__, url_prefix="")


@blp.before_request
def init_job_interface() -> None:  # pylint: disable=missing-function-docstring
    g.inter = InterfaceApiJob(user=g.user)


@blp.route("/jobs/<string:job_id>")
class ApiJobDetail(MethodView):
    """Read a JobState the current user owns."""

    @blp.response(200, JobResponseSchema)
    def get(self, job_id: str) -> ResponseReturnValue:
        """Return the full JobState envelope (status, dates, attempts, result, error)."""
        logger_api.debug("GET /jobs/%s user=%s", job_id, g.user.uid)
        interface: InterfaceApiJob = g.inter
        return interface.get_job(job_id)


@blp.route("/jobs/<string:job_id>/cancel")
class ApiJobCancel(MethodView):
    """Cancel a job the current user owns."""

    @blp.response(200, JobResponseSchema)
    def post(self, job_id: str) -> ResponseReturnValue:
        """Request cancellation and return the refreshed JobState (idempotent)."""
        logger_api.debug("POST /jobs/%s/cancel user=%s", job_id, g.user.uid)
        interface: InterfaceApiJob = g.inter
        return interface.cancel_job(job_id)


@blp.route("/jobs/<string:job_id>/result")
class ApiJobResult(MethodView):
    """Serve the large result blob produced by a completed Agent job."""

    @blp.arguments(JobResultQueryArgsSchema, location="query", arg_name="query_args")
    def get(self, query_args: dict, job_id: str) -> ResponseReturnValue:
        """Stream the job result with its native Content-Type.

        Defaults to inline; pass ``?download=true`` to force the browser to save the file.
        """
        logger_api.debug("GET /jobs/%s/result user=%s args=%s", job_id, g.user.uid, query_args)
        interface: InterfaceApiJob = g.inter
        return interface.get_result(job_id, download=bool(query_args.get("download")))
