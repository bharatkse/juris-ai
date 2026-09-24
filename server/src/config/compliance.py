from __future__ import annotations

from config.base import BaseAppSettings


class ComplianceSettings(BaseAppSettings):
    """
    Compliance/legal-discovery audit trail configuration.
    """

    # None = retain indefinitely. This is the safe default and stays
    # the default until someone sets it deliberately.
    #
    # Do not set this without confirmed legal/compliance retention
    # requirements for your jurisdiction and matter types -- this is
    # destructive and irreversible. Purging is a real DELETE against
    # compliance_log (see ComplianceLogService.purge_older_than()),
    # not a soft delete or archive, and nothing in this codebase calls
    # that method automatically: no scheduled job, no cron, no
    # background task. It only ever runs if explicitly invoked (e.g.
    # scripts/python/purge_compliance_log.py) with this value
    # populated -- guessing a number here to "ship the feature" would
    # mean guessing a legal retention policy, which is exactly what
    # this setting must never do on its own.
    COMPLIANCE_LOG_RETENTION_DAYS: int | None = None
