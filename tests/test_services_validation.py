"""
Unit tests for the pure service-directory validation rules.

These need no database and run with the standard library test runner:

    python -m unittest discover -s tests

They are intentionally limited to the rules that have no I/O: slug handling,
coordinate/provenance validation, primary-category resolution and the category
cycle guard. Database-backed behaviour is exercised by the opt-in integration
script in tests_manual/test_services_domain.py.
"""

import unittest

from app.core.exceptions import ServiceError
from app.models.service import ServiceStatus
from app.modules.services.validation import (
    clean_optional_text,
    normalise_slug,
    require_non_empty,
    resolve_primary_category,
    validate_category_selection,
    validate_contact_fields,
    validate_latitude,
    validate_location_pair,
    validate_longitude,
    validate_provenance,
    would_create_category_cycle,
)


class SlugTests(unittest.TestCase):
    def test_normalises_case_spaces_and_underscores(self):
        self.assertEqual(normalise_slug("  Persian_Rugs "), "persian-rugs")
        self.assertEqual(normalise_slug("Grocery  Store"), "grocery-store")

    def test_rejects_empty(self):
        with self.assertRaises(ServiceError):
            normalise_slug("   ")

    def test_rejects_non_latin(self):
        with self.assertRaises(ServiceError):
            normalise_slug("رستوران")


class TextTests(unittest.TestCase):
    def test_clean_optional_text_turns_blank_into_none(self):
        self.assertIsNone(clean_optional_text(""))
        self.assertIsNone(clean_optional_text("   "))
        self.assertIsNone(clean_optional_text(None))
        self.assertEqual(clean_optional_text("  hi "), "hi")

    def test_require_non_empty_raises_on_blank(self):
        with self.assertRaises(ServiceError):
            require_non_empty("  ", "name")
        self.assertEqual(require_non_empty(" x ", "name"), "x")

    def test_validate_contact_fields(self):
        self.assertEqual(validate_contact_fields(" Phone ", " 123 "), ("Phone", "123"))
        with self.assertRaises(ServiceError):
            validate_contact_fields("", "123")
        with self.assertRaises(ServiceError):
            validate_contact_fields("Phone", " ")


class LocationTests(unittest.TestCase):
    def test_latitude_bounds(self):
        self.assertIsNone(validate_latitude(None))
        self.assertEqual(validate_latitude(50.11), 50.11)
        with self.assertRaises(ServiceError):
            validate_latitude(91)

    def test_longitude_bounds(self):
        self.assertIsNone(validate_longitude(None))
        self.assertEqual(validate_longitude(8.68), 8.68)
        with self.assertRaises(ServiceError):
            validate_longitude(-181)

    def test_coordinates_must_be_a_pair(self):
        validate_location_pair(None, None)
        validate_location_pair(1.0, 2.0)
        with self.assertRaises(ServiceError):
            validate_location_pair(1.0, None)
        with self.assertRaises(ServiceError):
            validate_location_pair(None, 2.0)


class ProvenanceTests(unittest.TestCase):
    def test_both_or_neither(self):
        self.assertEqual(validate_provenance(None, None), (None, None))
        self.assertEqual(
            validate_provenance("atlas", "42"), ("atlas", "42")
        )
        with self.assertRaises(ServiceError):
            validate_provenance("atlas", None)
        with self.assertRaises(ServiceError):
            validate_provenance(None, "42")


class PrimaryCategoryTests(unittest.TestCase):
    def test_resolves_the_single_primary(self):
        self.assertEqual(resolve_primary_category([(1, False), (2, True)]), 2)
        self.assertIsNone(resolve_primary_category([(1, False), (2, False)]))
        self.assertIsNone(resolve_primary_category([]))

    def test_rejects_more_than_one_primary(self):
        with self.assertRaises(ServiceError):
            resolve_primary_category([(1, True), (2, True)])

    def test_draft_may_have_no_categories(self):
        validate_category_selection([], ServiceStatus.draft)

    def test_published_requires_a_category(self):
        with self.assertRaises(ServiceError):
            validate_category_selection([], ServiceStatus.published)

    def test_published_requires_exactly_one_primary(self):
        with self.assertRaises(ServiceError):
            validate_category_selection([(1, False)], ServiceStatus.published)
        validate_category_selection([(1, True)], ServiceStatus.published)
        validate_category_selection([(1, True), (2, False)], ServiceStatus.published)


class CategoryCycleTests(unittest.TestCase):
    # 1 -> None, 2 -> 1, 3 -> 2
    TREE = {1: None, 2: 1, 3: 2}

    def lookup(self, category_id):
        return self.TREE.get(category_id)

    def test_no_parent_is_never_a_cycle(self):
        self.assertFalse(would_create_category_cycle(1, None, self.lookup))

    def test_self_parent_is_a_cycle(self):
        self.assertTrue(would_create_category_cycle(2, 2, self.lookup))

    def test_moving_under_a_descendant_is_a_cycle(self):
        # Move category 1 under category 3 (which is a descendant of 1).
        self.assertTrue(would_create_category_cycle(1, 3, self.lookup))

    def test_sibling_is_not_a_cycle(self):
        # 2 and 3 are siblings under 1; moving 2 under 3 is allowed.
        siblings = {1: None, 2: 1, 3: 1}
        self.assertFalse(
            would_create_category_cycle(2, 3, lambda cid: siblings.get(cid))
        )

    def test_unrelated_move_is_not_a_cycle(self):
        # Move category 3 under category 1 (its ancestor): allowed, no cycle.
        self.assertFalse(would_create_category_cycle(3, 1, self.lookup))

    def test_pre_existing_loop_does_not_hang(self):
        # A corrupt tree must not cause an infinite walk.
        loop = {1: 2, 2: 1}
        self.assertFalse(
            would_create_category_cycle(3, 1, lambda cid: loop.get(cid))
        )


if __name__ == "__main__":
    unittest.main()
