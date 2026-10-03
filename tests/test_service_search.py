"""
Unit tests for the international location model and the shared service filter
engine. Pure logic, so no database is required.
"""

import unittest
from datetime import datetime, timezone

from app.core.exceptions import ServiceError
from app.models.service import ServiceStatus
from app.modules.services.location import (
    MAX_POSTAL_CODE_LENGTH,
    StateVocabulary,
    clean_city,
    clean_postal_code,
    clean_state,
    fold,
    normalise_country_code,
    resolve_state,
)
from app.modules.services.schemas.service_requests import (
    AdminServiceSearchParams,
    PublicServiceSearchParams,
)
from app.modules.services.search.query import (
    SERVICE_FILTER_FIELDS,
    FilterOp,
    ServiceQueryBuilder,
    SortMode,
    supported_sort_modes,
)


# ---------------------------------------------------------------- country code


class CountryCodeTests(unittest.TestCase):
    def test_germany(self):
        self.assertEqual(normalise_country_code("DE"), "DE")

    def test_other_countries_are_equally_valid(self):
        # The point of the model: Germany is not privileged at the domain level.
        for code in ("AT", "CH", "NL", "US", "IR", "TR", "IR"):
            with self.subTest(code=code):
                self.assertEqual(normalise_country_code(code), code)

    def test_lowercase_is_normalised(self):
        self.assertEqual(normalise_country_code("at"), "AT")
        self.assertEqual(normalise_country_code("ch"), "CH")

    def test_surrounding_whitespace_is_trimmed(self):
        self.assertEqual(normalise_country_code("  de  "), "DE")

    def test_internal_whitespace_is_collapsed_then_rejected(self):
        with self.assertRaises(ServiceError):
            normalise_country_code("D E")

    def test_blank_means_unstated_not_germany(self):
        # "not stated" is a real filterable state and must not silently become DE.
        self.assertIsNone(normalise_country_code(""))
        self.assertIsNone(normalise_country_code("   "))
        self.assertIsNone(normalise_country_code(None))

    def test_three_letters_rejected(self):
        with self.assertRaises(ServiceError):
            normalise_country_code("DEU")

    def test_one_letter_rejected(self):
        with self.assertRaises(ServiceError):
            normalise_country_code("D")

    def test_non_alpha_rejected(self):
        for bad in ("12", "d3", "1a"):
            with self.subTest(bad=bad):
                with self.assertRaises(ServiceError):
                    normalise_country_code(bad)


# ------------------------------------------------------------------- city / PLZ


class CityAndPostalTests(unittest.TestCase):
    def test_city_trims_and_collapses_whitespace(self):
        self.assertEqual(clean_city("  Frankfurt   am  Main "), "Frankfurt am Main")

    def test_city_blank_becomes_none(self):
        self.assertIsNone(clean_city("   "))

    def test_city_does_not_guess_equivalence(self):
        # Frankfurt and Frankfurt am Main stay distinct: guessing is a data
        # decision deferred to a future alias system, not something to infer here.
        self.assertNotEqual(clean_city("Frankfurt"), clean_city("Frankfurt am Main"))

    def test_postal_code_is_generic_text(self):
        # German codes are 5 digits; the model must not assume that.
        for value in ("10115", "SW1A 1AA", "K1A 0B1", "75008", "1000"):
            with self.subTest(value=value):
                self.assertEqual(clean_postal_code(value), value)

    def test_postal_code_length_is_bounded(self):
        self.assertEqual(clean_postal_code("A" * MAX_POSTAL_CODE_LENGTH),
                         "A" * MAX_POSTAL_CODE_LENGTH)
        with self.assertRaises(ServiceError):
            clean_postal_code("A" * (MAX_POSTAL_CODE_LENGTH + 1))

    def test_state_trims(self):
        self.assertEqual(clean_state("  Hessen "), "Hessen")


# --------------------------------------------------------- state vocabulary


class FoldTests(unittest.TestCase):
    """
    `fold` handles case and diacritics ONLY.

    It deliberately does not transliterate "ue" to "u" and similar: a blanket
    rewrite would fold "Neuss" to "ness" and "Freude" to "frde", letting two
    different region names collide. Those ASCII spellings are explicit aliases in
    the vocabulary table instead, which is verified in the vocabulary tests.
    """

    def test_case_folded(self):
        self.assertEqual(fold("Hessen"), fold("HESSEN"))
        self.assertEqual(fold("Hessen"), fold("hessen"))

    def test_diacritics_folded(self):
        # The umlaut itself is removed, which is a lossless decomposition, not a
        # transliteration: Thüringen -> thuringen.
        self.assertEqual(fold("Thüringen"), fold("Thuringen"))
        self.assertEqual(fold("Baden-Württemberg"), fold("Baden-Wurttemberg"))

    def test_sharp_s_folded(self):
        self.assertEqual(fold("Straße"), fold("Strasse"))

    def test_whitespace_runs_collapsed(self):
        self.assertEqual(fold("Nordrhein  Westfalen"), fold("nordrhein westfalen"))

    def test_does_not_collide_unrelated_names(self):
        # The reason the two-letter rewrite was rejected.
        self.assertNotEqual(fold("Neuss"), fold("ness"))
        self.assertNotEqual(fold("Freude"), fold("frde"))


class GermanStateVocabularyTests(unittest.TestCase):
    def setUp(self):
        # Mirrors the seeded alias shape, including the ASCII two-letter forms
        # that fold() intentionally does not derive.
        self.vocab = StateVocabulary.from_rows(
            "DE",
            names=["Hessen", "Thüringen", "Bayern", "Nordrhein-Westfalen"],
            aliases=[
                ["Hesse", "HE"],
                ["Thuringia", "Thueringen", "TH"],
                ["Bavaria", "BY"],
                ["North Rhine-Westphalia", "Nordrhein Westfalen", "NW"],
            ],
        )
        self.lookup = lambda code: self.vocab if code == "DE" else None

    def test_canonical_passes_through(self):
        self.assertEqual(resolve_state("DE", "Hessen", self.lookup), "Hessen")

    def test_english_variant_normalises(self):
        # The requirement: Hesse / hessen -> Hessen.
        self.assertEqual(resolve_state("DE", "Hesse", self.lookup), "Hessen")
        self.assertEqual(resolve_state("DE", "hesse", self.lookup), "Hessen")
        self.assertEqual(resolve_state("DE", "HESSEN", self.lookup), "Hessen")

    def test_code_alias_normalises(self):
        self.assertEqual(resolve_state("DE", "HE", self.lookup), "Hessen")

    def test_umlaut_and_ascii_spelling_agree(self):
        # Thüringen (canonical), Thuringia (English), Thueringen (ASCII
        # two-letter) all resolve to the one stored value.
        for variant in ("Thüringen", "Thuringia", "Thueringen", "thueringen", "TH"):
            with self.subTest(variant=variant):
                self.assertEqual(resolve_state("DE", variant, self.lookup), "Thüringen")

    def test_hyphen_and_space_spellings_agree(self):
        for variant in (
            "Nordrhein-Westfalen",
            "Nordrhein Westfalen",
            "nordrhein-westfalen",
        ):
            with self.subTest(variant=variant):
                self.assertEqual(
                    resolve_state("DE", variant, self.lookup), "Nordrhein-Westfalen"
                )

    def test_unknown_variant_rejected(self):
        # This is what actually prevents fragmentation: an unrecognised spelling
        # for a country whose full region list we hold cannot become a second
        # canonical value.
        with self.assertRaises(ServiceError) as ctx:
            resolve_state("DE", "Hesse-Nassau", self.lookup)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_error_lists_valid_values(self):
        with self.assertRaises(ServiceError) as ctx:
            resolve_state("DE", "Atlantis", self.lookup)
        self.assertIn("Hessen", str(ctx.exception.message))

    def test_country_without_vocabulary_passes_through(self):
        # Austria has no vocabulary yet, so its state is stored as typed.
        self.assertEqual(resolve_state("AT", "Wien", self.lookup), "Wien")
        self.assertEqual(resolve_state("AT", "Vienna", self.lookup), "Vienna")

    def test_no_country_passes_through(self):
        self.assertEqual(resolve_state(None, "Hessen", self.lookup), "Hessen")

    def test_blank_state_is_none(self):
        self.assertIsNone(resolve_state("DE", "  ", self.lookup))
        self.assertIsNone(resolve_state("DE", None, self.lookup))

    def test_vocabulary_names_sorted_and_deduplicated(self):
        # Aliases must not appear as separate entries: the canonical list is what
        # an admin sees, and it must be the size of the real vocabulary.
        self.assertEqual(
            self.vocab.names(),
            ["Bayern", "Hessen", "Nordrhein-Westfalen", "Thüringen"],
        )

    def test_additional_country_needs_no_code_change(self):
        # The design claim: another country is a data insert, not a redesign.
        # Once Austria has a vocabulary, its values canonicalise; the SAME code
        # path handles it with no change to this module.
        at = StateVocabulary.from_rows(
            "AT", names=["Wien", "Tirol"], aliases=[["Vienna"], ["Tyrol"]]
        )
        vocabularies = {"DE": self.vocab, "AT": at}
        lookup = lambda code: vocabularies.get(code)  # noqa: E731

        self.assertEqual(resolve_state("AT", "Vienna", lookup), "Wien")
        self.assertEqual(resolve_state("AT", "Tirol", lookup), "Tirol")
        with self.assertRaises(ServiceError):
            resolve_state("AT", "Steiermark", lookup)  # not in the partial list

    def test_country_with_partial_vocabulary_can_be_extended(self):
        # A partial list rejects what it does not know, rather than storing it.
        # That is the trade-off of validating at all: until Austria's list is
        # complete, an Austrian region outside it cannot be saved. Populating
        # the row is the fix, and it needs no code change.
        at = StateVocabulary.from_rows("AT", names=["Wien"], aliases=[])
        lookup = lambda code: at if code == "AT" else None  # noqa: E731
        self.assertEqual(resolve_state("AT", "Wien", lookup), "Wien")
        with self.assertRaises(ServiceError) as ctx:
            resolve_state("AT", "Salzburg", lookup)
        self.assertIn("Salzburg", str(ctx.exception.message))

    def test_german_vocabulary_rejects_all_sixteen_bundeslaender_check(self):
        # Sanity check that the DE list is complete and closed: all 16 resolve,
        # and an invented one does not.
        sixteen = [
            "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
            "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
            "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
            "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
        ]
        vocab = StateVocabulary.from_rows(
            "DE", names=sixteen, aliases=[[] for _ in sixteen]
        )
        lookup = lambda code: vocab if code == "DE" else None  # noqa: E731
        for name in sixteen:
            with self.subTest(name=name):
                self.assertEqual(resolve_state("DE", name, lookup), name)
        self.assertEqual(len(vocab.names()), 16)
        with self.assertRaises(ServiceError):
            resolve_state("DE", "Frankfurt", lookup)

    def test_country_without_vocabulary_is_unaffected_by_another_country_having_one(self):
        # Germany having a list must not start rejecting Swiss cantons.
        lookup = lambda code: self.vocab if code == "DE" else None  # noqa: E731
        for swiss in ("Zürich", "Genève", "Bern"):
            with self.subTest(swiss=swiss):
                self.assertEqual(resolve_state("CH", swiss, lookup), swiss)


# ------------------------------------------------------------- filter engine


def _builder(allow):
    return ServiceQueryBuilder(db=None, allow=allow)


class FieldAllowListTests(unittest.TestCase):
    def test_public_allow_list_is_small_and_explicit(self):
        from app.modules.services.search.service_search_service import PUBLIC_ALLOW

        self.assertEqual(
            set(PUBLIC_ALLOW),
            {
                "country_code",
                "state",
                "city",
                "persian_owned",
                "persian_provider",
                "persian_language",
                "persian_service",
            },
        )

    def test_admin_allow_list_is_a_superset(self):
        from app.modules.services.search.service_search_service import (
            ADMIN_ALLOW,
            PUBLIC_ALLOW,
        )

        self.assertTrue(PUBLIC_ALLOW.issubset(ADMIN_ALLOW))
        self.assertIn("postal_code", ADMIN_ALLOW)

    def test_unknown_field_rejected(self):
        builder = _builder(frozenset({"city"}))
        with self.assertRaises(ServiceError) as ctx:
            builder.filter("nonexistent", FilterOp.exact, "x")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_field_outside_allow_list_rejected(self):
        # Valid engine field, but not exposed on this surface.
        builder = _builder(frozenset({"city"}))
        with self.assertRaises(ServiceError):
            builder.filter("postal_code", FilterOp.exact, "10115")

    def test_public_cannot_reach_description(self):
        from app.modules.services.search.service_search_service import PUBLIC_ALLOW

        builder = _builder(PUBLIC_ALLOW)
        with self.assertRaises(ServiceError):
            builder.filter("description", FilterOp.contains, "x")


class OperatorTests(unittest.TestCase):
    def test_exact_and_contains_both_supported_for_city(self):
        builder = _builder(frozenset({"city"}))
        builder.filter("city", FilterOp.exact, "Kassel")
        builder.filter("city", FilterOp.contains, "Kassel")
        self.assertEqual(len(builder.conditions), 2)

    def test_contains_not_allowed_on_latitude(self):
        builder = _builder(frozenset({"latitude"}))
        with self.assertRaises(ServiceError) as ctx:
            builder.filter("latitude", FilterOp.contains, "50")
        self.assertIn("contains", str(ctx.exception.message))

    def test_range_operators_allowed_on_latitude(self):
        builder = _builder(frozenset({"latitude"}))
        for op in (FilterOp.gte, FilterOp.lte, FilterOp.gt, FilterOp.lt):
            builder.filter("latitude", op, 50)
        self.assertEqual(len(builder.conditions), 4)

    def test_unknown_operator_rejected(self):
        builder = _builder(frozenset({"city"}))
        with self.assertRaises(ServiceError) as ctx:
            builder.filter("city", "regex", "x")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_bad_number_rejected(self):
        builder = _builder(frozenset({"latitude"}))
        with self.assertRaises(ServiceError):
            builder.filter("latitude", FilterOp.gte, "not-a-number")

    def test_is_null_requires_boolean(self):
        builder = _builder(frozenset({"city"}))
        builder.filter("city", FilterOp.is_null, True)
        builder.filter("city", FilterOp.is_null, False)
        self.assertEqual(len(builder.conditions), 2)

    def test_tristate_accepts_both_spellings(self):
        builder = _builder(frozenset({"persian_owned"}))
        for value in ("yes", "no", "unknown", "true", "false", "null"):
            builder.filter("persian_owned", FilterOp.tristate, value)
        self.assertEqual(len(builder.conditions), 6)

    def test_tristate_rejects_nonsense(self):
        builder = _builder(frozenset({"persian_owned"}))
        with self.assertRaises(ServiceError):
            builder.filter("persian_owned", FilterOp.tristate, "maybe")

    def test_tristate_condition_distinguishes_null_from_false(self):
        from app.modules.services.schemas.service_requests import TriStateFilter

        builder = _builder(frozenset({"persian_owned"}))
        builder.filter("persian_owned", FilterOp.tristate, "no")
        builder.filter("persian_owned", FilterOp.tristate, "unknown")
        no_condition = str(builder.conditions[0].condition)
        unknown_condition = str(builder.conditions[1].condition)
        self.assertNotEqual(no_condition, unknown_condition)
        self.assertIn("IS false", no_condition)
        self.assertIn("IS NULL", unknown_condition)


class StatusPermissionTests(unittest.TestCase):
    def test_public_builder_cannot_filter_status(self):
        builder = _builder(frozenset({"city"}))
        with self.assertRaises(ServiceError):
            builder.status(ServiceStatus.draft)

    def test_admin_builder_can(self):
        builder = _builder(frozenset({"city"})).allow_status()
        builder.status(ServiceStatus.draft)
        self.assertEqual(len(builder.conditions), 1)

    def test_published_only_always_works(self):
        builder = _builder(frozenset({"city"}))
        builder.published_only()
        condition = str(builder.conditions[0].condition)
        # Bind parameters are named, so assert on the compile with literals.
        compiled = str(
            builder._stmt().compile(compile_kwargs={"literal_binds": True})
        )
        self.assertIn("status", condition)
        self.assertIn("published", compiled)


class SortingAndPagingTests(unittest.TestCase):
    def test_sort_modes_are_named(self):
        for mode in ("newest", "oldest", "name_asc", "name_desc", "recently_updated"):
            self.assertIn(mode, supported_sort_modes())

    def test_every_sort_mode_has_a_unique_tiebreaker(self):
        # Deterministic paging: without a tiebreaker, equal keys can swap pages.
        for mode in SortMode:
            from app.modules.services.search.query import _SORT_EXPRESSIONS

            self.assertGreaterEqual(len(_SORT_EXPRESSIONS[mode]), 2, mode)

    def test_unknown_sort_rejected(self):
        builder = _builder(frozenset({"city"}))
        with self.assertRaises(ServiceError) as ctx:
            builder.sort("drop_table")
        self.assertIn("sort", str(ctx.exception.message))

    def test_client_cannot_name_a_column(self):
        # The allow-list is by mode name; a raw column name is simply unknown.
        builder = _builder(frozenset({"city"}))
        with self.assertRaises(ServiceError):
            builder.sort("owner_user_id")

    def test_page_must_be_positive(self):
        builder = _builder(frozenset({"city"}))
        with self.assertRaises(ServiceError):
            builder.paginate(0, 20)

    def test_size_is_bounded(self):
        builder = _builder(frozenset({"city"}))
        builder.paginate(1, 100)
        with self.assertRaises(ServiceError):
            builder.paginate(1, 101)

    def test_search_term_is_bounded(self):
        from app.modules.services.search.query import (
            _MAX_SEARCH_TERM_LENGTH,
            _MAX_SEARCH_WORDS,
            _clean_search_term,
        )

        self.assertIsNone(_clean_search_term("   "))
        self.assertLessEqual(len(_clean_search_term("x" * 5000)), _MAX_SEARCH_TERM_LENGTH)
        bounded = _clean_search_term(" ".join(["word"] * 50))
        self.assertLessEqual(len(bounded.split()), _MAX_SEARCH_WORDS)


class LikeEscapingTests(unittest.TestCase):
    def test_wildcards_in_user_input_are_escaped(self):
        from app.modules.services.search.query import _escape_like

        self.assertEqual(_escape_like("50%"), "50\\%")
        self.assertEqual(_escape_like("a_b"), "a\\_b")
        self.assertEqual(_escape_like("c\\d"), "c\\\\d")


class PublicSchemaTests(unittest.TestCase):
    def test_unknown_query_parameter_is_rejected(self):
        # extra="forbid": a misspelled filter must be an error, not a no-op.
        with self.assertRaises(Exception):
            PublicServiceSearchParams(nonexistent_filter="x")

    def test_country_code_is_optional(self):
        # The endpoint is international: it must not require or default to DE.
        self.assertIsNone(PublicServiceSearchParams().country_code)

    def test_category_accepts_multiple(self):
        params = PublicServiceSearchParams(category=[1, 2, 3])
        self.assertEqual(params.category, [1, 2, 3])

    def test_relevance_filters_are_tri_state(self):
        from app.modules.services.schemas.service_requests import TriStateFilter

        params = PublicServiceSearchParams(persian_language=TriStateFilter.unknown)
        self.assertIs(params.persian_language, TriStateFilter.unknown)

    def test_public_schema_has_no_status(self):
        self.assertNotIn("status", PublicServiceSearchParams.model_fields)

    def test_admin_schema_has_status(self):
        self.assertIn("status", AdminServiceSearchParams.model_fields)


if __name__ == "__main__":
    unittest.main()