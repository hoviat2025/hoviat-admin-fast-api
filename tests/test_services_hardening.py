"""
Unit tests for the hardening-pass rules: retired (inactive) category handling
and optimistic-concurrency timestamp comparison.

Pure functions, so no database is involved.
"""

import unittest
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.core.exceptions import ServiceError
from app.models.service import ServiceStatus
from app.modules.admin.service_management.schemas.list_services import ServiceListQuery
from app.modules.services.schemas.service_requests import (
    ServiceAggregateSaveRequest,
    ServiceCreateRequest,
    ServiceUpdateRequest,
    TriStateFilter,
)
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
        # Internal callers may omit the token; the row lock still serialises
        # them. The HTTP endpoint itself now requires one (see the schema tests).
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


class TriStateRelevanceTests(unittest.TestCase):
    """
    The four Iranian/Persian signals are tri-state: True = explicitly yes,
    False = explicitly no, None = not assessed. Unknown must survive as None and
    must never be silently treated as False.
    """

    FIELDS = (
        "persian_owned",
        "persian_provider",
        "persian_language",
        "persian_service",
    )

    def _create(self, **overrides):
        return ServiceCreateRequest(name="Praxis", **overrides)

    def test_create_defaults_every_signal_to_unknown(self):
        created = self._create()
        for field in self.FIELDS:
            with self.subTest(field=field):
                self.assertIsNone(getattr(created, field))

    def test_every_signal_accepts_all_three_states(self):
        for field in self.FIELDS:
            for value in (True, False, None):
                with self.subTest(field=field, value=value):
                    created = self._create(**{field: value})
                    self.assertEqual(getattr(created, field), value)

    def test_provider_is_independent_of_owner(self):
        # The motivating case: a German-owned clinic with an Iranian dentist.
        created = self._create(persian_owned=False, persian_provider=True)
        self.assertFalse(created.persian_owned)
        self.assertTrue(created.persian_provider)

    def test_signals_are_independent_of_each_other(self):
        created = self._create(
            persian_owned=True,
            persian_provider=False,
            persian_language=True,
            persian_service=None,
        )
        self.assertTrue(created.persian_owned)
        self.assertFalse(created.persian_provider)
        self.assertTrue(created.persian_language)
        self.assertIsNone(created.persian_service)

    def test_partial_update_absent_key_means_untouched(self):
        update = ServiceUpdateRequest(relevance={"persian_language": True})
        dumped = update.model_dump(exclude_unset=True)
        # Only the key that was actually sent survives, so the update cannot
        # wipe the other three back to unknown.
        self.assertEqual(list(dumped["relevance"]), ["persian_language"])

    def test_partial_update_explicit_null_means_unknown(self):
        update = ServiceUpdateRequest(
            relevance={"persian_owned": False, "persian_service": None}
        )
        dumped = update.model_dump(exclude_unset=True)
        self.assertIs(dumped["relevance"]["persian_owned"], False)
        self.assertIn("persian_service", dumped["relevance"])
        self.assertIsNone(dumped["relevance"]["persian_service"])


class LocationScopeTests(unittest.TestCase):
    """
    Location is international, presented Germany-first.

    `country_code` is the canonical ISO-3166-1 alpha-2 identifier; `DE` is only
    the default the admin sees, not a domain rule.
    """

    def test_country_code_defaults_to_de(self):
        # Presentation default, not an invariant: see CountryCodeTests for the
        # proof that other countries are equally valid.
        self.assertEqual(ServiceCreateRequest(name="Praxis").country_code, "DE")

    def test_country_code_can_be_overridden(self):
        created = ServiceCreateRequest(name="Praxis", country_code="AT")
        self.assertEqual(created.country_code, "AT")

    def test_state_is_accepted(self):
        created = ServiceCreateRequest(name="Praxis", state="Hessen")
        self.assertEqual(created.state, "Hessen")

    def test_state_defaults_to_none(self):
        self.assertIsNone(ServiceCreateRequest(name="Praxis").state)

    def test_state_concept_is_not_germany_specific(self):
        # The field is the generic "first-level administrative region"; only the
        # stored vocabulary happens to be German for now.
        created = ServiceCreateRequest(
            name="Praxis", country_code="CH", state="Zürich"
        )
        self.assertEqual(created.state, "Zürich")


class AggregateConcurrencyTokenTests(unittest.TestCase):
    def test_expected_updated_at_is_required(self):
        with self.assertRaises(ValidationError) as ctx:
            ServiceAggregateSaveRequest(name="Praxis")
        self.assertIn("expected_updated_at", str(ctx.exception))

    def test_expected_updated_at_parses_an_iso_string(self):
        request = ServiceAggregateSaveRequest(
            name="Praxis", expected_updated_at="2026-01-01T12:00:00.123Z"
        )
        self.assertIsInstance(request.expected_updated_at, datetime)
        self.assertEqual(
            truncate_to_millis(request.expected_updated_at),
            datetime(2026, 1, 1, 12, 0, 0, 123000, tzinfo=timezone.utc),
        )

    def test_expected_updated_at_rejects_garbage(self):
        with self.assertRaises(ValidationError):
            ServiceAggregateSaveRequest(name="Praxis", expected_updated_at="not-a-date")


class TriStateFilterTests(unittest.TestCase):
    """The admin filters must be able to select the unknown rows."""

    def test_filter_values(self):
        self.assertEqual(
            {f.value for f in TriStateFilter}, {"yes", "no", "unknown"}
        )

    def test_filter_parses_from_query_string(self):
        query = ServiceListQuery(persian_language="unknown", state="Hessen")
        self.assertIs(query.persian_language, TriStateFilter.unknown)
        self.assertEqual(query.state, "Hessen")

    def test_filter_rejects_a_nonsense_value(self):
        with self.assertRaises(ValidationError):
            ServiceListQuery(persian_language="maybe")


if __name__ == "__main__":
    unittest.main()