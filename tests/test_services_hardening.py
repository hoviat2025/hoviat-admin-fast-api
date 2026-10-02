"""
Unit tests for the hardening-pass rules: retired (inactive) category handling
and optimistic-concurrency timestamp comparison.

Pure functions, so no database is involved.
"""

import unittest
from datetime import datetime, timedelta, timezone

from app.core.exceptions import ServiceError
from app.models.service import ServiceStatus
from app.modules.services.validation import (
    truncate_to_millis,
    updated_at_conflicts,
    validate_category_assignments,
)

ACTIVE = {1: True, 2: True}
MIXED = {1: True, 2: False}


class InactiveCategoryTests(unittest.TestCase):
    def test_active_categories_assign_freely(self):
        validate_category_assignments(
            [(1, True), (2, False)],
            active_by_id=ACTIVE,
            currently_assigned=set(),
            current_primary_id=None,
            status=ServiceStatus.draft,
        )

    def test_inactive_cannot_be_newly_assigned(self):
        with self.assertRaises(ServiceError) as ctx:
            validate_category_assignments(
                [(2, False)],
                active_by_id=MIXED,
                currently_assigned=set(),
                current_primary_id=None,
                status=ServiceStatus.draft,
            )
        self.assertIn("inactive", str(ctx.exception.message))

    def test_existing_inactive_assignment_may_be_preserved(self):
        # Already assigned before the category was retired: keeping it is fine.
        validate_category_assignments(
            [(2, False)],
            active_by_id=MIXED,
            currently_assigned={2},
            current_primary_id=None,
            status=ServiceStatus.draft,
        )

    def test_existing_inactive_assignment_may_be_removed(self):
        # Dropping it entirely is always allowed.
        validate_category_assignments(
            [],
            active_by_id=MIXED,
            currently_assigned={2},
            current_primary_id=None,
            status=ServiceStatus.draft,
        )

    def test_inactive_cannot_newly_become_primary(self):
        with self.assertRaises(ServiceError):
            validate_category_assignments(
                [(2, True)],
                active_by_id=MIXED,
                currently_assigned={2},
                current_primary_id=None,
                status=ServiceStatus.draft,
            )

    def test_already_primary_inactive_may_stay_primary_on_a_draft(self):
        # It was the primary before it was retired; we do not silently demote it.
        validate_category_assignments(
            [(2, True)],
            active_by_id=MIXED,
            currently_assigned={2},
            current_primary_id=2,
            status=ServiceStatus.draft,
        )

    def test_published_requires_an_active_primary(self):
        with self.assertRaises(ServiceError):
            validate_category_assignments(
                [(2, True)],
                active_by_id=MIXED,
                currently_assigned={2},
                current_primary_id=2,
                status=ServiceStatus.published,
            )

    def test_published_with_active_primary_is_fine(self):
        validate_category_assignments(
            [(1, True), (2, False)],
            active_by_id=MIXED,
            currently_assigned={1, 2},
            current_primary_id=1,
            status=ServiceStatus.published,
        )

    def test_unknown_category_is_404(self):
        with self.assertRaises(ServiceError) as ctx:
            validate_category_assignments(
                [(99, False)],
                active_by_id=ACTIVE,
                currently_assigned=set(),
                current_primary_id=None,
                status=ServiceStatus.draft,
            )
        self.assertEqual(ctx.exception.status_code, 404)


class OptimisticConcurrencyTests(unittest.TestCase):
    def test_no_token_means_no_optimistic_check(self):
        now = datetime.now(timezone.utc)
        self.assertFalse(updated_at_conflicts(now, None))

    def test_equal_timestamps_do_not_conflict(self):
        moment = datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
        self.assertFalse(updated_at_conflicts(moment, moment))

    def test_javascript_millisecond_precision_does_not_false_conflict(self):
        # The browser can only carry milliseconds; the row has microseconds.
        stored = datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
        from_browser = datetime(2026, 1, 1, 12, 0, 0, 123000, tzinfo=timezone.utc)
        self.assertFalse(updated_at_conflicts(stored, from_browser))

    def test_a_later_write_conflicts(self):
        stored = datetime(2026, 1, 1, 12, 0, 0, 500000, tzinfo=timezone.utc)
        loaded = stored - timedelta(seconds=30)
        self.assertTrue(updated_at_conflicts(stored, loaded))

    def test_truncate_to_millis(self):
        self.assertIsNone(truncate_to_millis(None))
        self.assertEqual(
            truncate_to_millis(
                datetime(2026, 1, 1, 0, 0, 0, 123456, tzinfo=timezone.utc)
            ),
            datetime(2026, 1, 1, 0, 0, 0, 123000, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main()