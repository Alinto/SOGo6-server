from marshmallow import Schema, fields

from app.utils.api.ApiBaseResponse import ApiBaseResponse


class JobResultQueryArgsSchema(Schema):
    """Query string for the job result endpoint."""

    download = fields.Boolean(
        load_default=False,
        metadata={"description": "When true, the response carries a Content-Disposition: attachment header to trigger a browser download. Otherwise the result is served inline with its native Content-Type."},
    )


class JobStateSchema(Schema):
    """Minimal public view of a JobState - what the polling UI actually needs."""

    status  = fields.String(required=True, metadata={"description": "One of: pending / started / success / failure / retry / canceled."})
    payload = fields.Dict(metadata={"description": "Job-specific input echoed back to the owner, redacted of internal references (free-form: the keys depend on the job type)."})
    result  = fields.Dict(allow_none=True, metadata={"description": "Small job-specific result, free-form (e.g. import counters). A large blob result is not inlined - download it from /jobs/<id>/result."})
    error   = fields.String(allow_none=True, metadata={"description": "Error message when status is FAILURE, otherwise null."})


class JobResponseSchema(ApiBaseResponse):
    """Response schema for a single job."""

    data = fields.Nested(JobStateSchema, allow_none=True)
