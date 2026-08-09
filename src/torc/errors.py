"""Explicit TORC domain failures."""


class TorcError(Exception):
    """Base class for expected domain failures."""


class IntegrityError(TorcError):
    """Stored provenance or content integrity is invalid."""


class LeaseConflictError(TorcError):
    """An authoritative lease conflicts with current authority."""


class ProjectionBudgetError(TorcError):
    """Required continuity material cannot fit in a projection budget."""


class HandoffError(TorcError):
    """A handoff cannot be prepared or resolved."""


class RollbackError(TorcError):
    """A requested append-only rollback is invalid."""


class BranchError(TorcError):
    """A requested new lineage branch is invalid."""


class NotFoundError(TorcError):
    """A requested TORC record does not exist."""
