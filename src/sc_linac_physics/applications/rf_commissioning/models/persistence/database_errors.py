"""Shared exceptions for RF commissioning persistence."""


class RecordConflictError(Exception):
    """Raised when optimistic locking detects a conflict."""

    def __init__(
        self, record_id: int, expected_version: int, actual_version: int
    ):
        self.record_id = record_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Record {record_id} was modified by another user. "
            f"Expected version {expected_version}, found {actual_version}."
        )


class RecordDeletionDisabledError(Exception):
    """Raised when record deletion is blocked by data-retention policy."""

    def __init__(self, record_id: int):
        self.record_id = record_id
        super().__init__(
            f"Deletion is disabled for commissioning record {record_id}. "
            "Archive or mark the workflow state instead."
        )
