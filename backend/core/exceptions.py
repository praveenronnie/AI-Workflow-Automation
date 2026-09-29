"""Domain exceptions mapped to HTTP responses by a single app-level handler."""


class NotFoundError(Exception):
    """Requested entity does not exist."""


class PermissionDeniedError(Exception):
    """Caller is not allowed to perform this operation."""


class ValidationError(Exception):
    """Request payload failed domain validation."""


class BrokerUnavailableError(Exception):
    """Task broker could not be reached for job dispatch."""


class PipelineUnavailableError(Exception):
    """A required AI pipeline component is not available."""


class ConflictError(Exception):
    """Operation conflicts with current resource state."""