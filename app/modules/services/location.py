"""
Location normalisation for the service domain.

Two jobs, deliberately separated:

  * **country_code** is canonicalised structurally, with no country list at all.
    It is an ISO-3166-1 alpha-2 code: uppercased and validated as two ASCII
    letters. Nothing here knows that Germany exists, so adding a country is data.

  * **state** is canonicalised *only where a vocabulary exists*. Germany has one
    (the 16 Bundeslaender); other countries currently do not, and for those the
    value is passed through as trimmed text. This is what keeps the design
    international: the normalisation is country-scoped and degrades to
    pass-through rather than to rejection.

The module is pure apart from the repository lookup for the vocabulary, so the
matching rules can be unit-tested without a database.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Optional

from app.core.exceptions import ServiceError

# ISO-3166-1 alpha-2: two ASCII letters. We do NOT check membership against a
# country list on purpose — the product must not be able to store a country just
# because we have not enumerated it yet, and an allow-list would need a
# maintenance migration every time one is added.
COUNTRY_CODE_PATTERN = re.compile(r"^[A-Z]{2}$")

# Postal codes are deliberately NOT constrained to digits. Germany uses five
# digits, but many countries use alphanumeric codes (GB, NL, CA, ...), and
# putting a German rule in the shared model would corrupt their data.
MAX_POSTAL_CODE_LENGTH = 32

# Collapses runs of whitespace so that "Frankfurt  am   Main" and
# "Frankfurt am Main" produce the same comparison key.
_WHITESPACE_RUN = re.compile(r"\s+")


def normalise_country_code(value: Optional[str]) -> Optional[str]:
    """
    Canonicalise a country code to uppercase ISO-3166-1 alpha-2.

    Accepts whatever casing and spacing the admin typed. Returns None for an
    empty value, because "country not stated" is a real, filterable state and
    must not be confused with a specific country.
    """
    if value is None:
        return None
    cleaned = _WHITESPACE_RUN.sub(" ", str(value)).strip()
    if not cleaned:
        return None
    upper = cleaned.upper()
    if not COUNTRY_CODE_PATTERN.match(upper):
        raise ServiceError(
            "INVALID_INPUT",
            "country_code must be a two-letter country code such as DE, AT or CH",
            422,
        )
    return upper


def clean_city(value: Optional[str]) -> Optional[str]:
    """
    Trim and collapse internal whitespace runs.

    Deliberately does far less than it might: "Frankfurt" and
    "Frankfurt am Main" are left distinct. Guessing that they are the same
    place is a data-model decision that needs real evidence, and the report
    flags it as a future alias/city-entity system rather than something to
    guess at here.
    """
    return _clean_text(value)


def clean_postal_code(value: Optional[str]) -> Optional[str]:
    """Trim and length-check. No format or charset rules at the model level."""
    cleaned = _clean_text(value)
    if cleaned is not None and len(cleaned) > MAX_POSTAL_CODE_LENGTH:
        raise ServiceError(
            "INVALID_INPUT",
            f"postal_code must be at most {MAX_POSTAL_CODE_LENGTH} characters",
            422,
        )
    return cleaned


def clean_state(value: Optional[str]) -> Optional[str]:
    """Trim and collapse whitespace. Canonical spelling is applied separately."""
    return _clean_text(value)


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    collapsed = _WHITESPACE_RUN.sub(" ", str(value)).strip()
    return collapsed or None


def fold(value: str) -> str:
    """
    Case- and diacritic-insensitive comparison key.

    Folds case and strips combining marks, so "Thüringen", "Thuringen" and
    "THÜRINGEN" all reduce to "thuringen", and "Baden-Württemberg" to
    "baden-wurttemberg".

    Deliberately NOT doing the "ue -> u" transliteration. It looks tempting, but
    it is not safe: "Neuss" would fold to "ness" and "Freude" to "frde", so two
    genuinely different region names could collide and a lookup could resolve to
    the wrong one. The ASCII two-letter spellings are therefore listed as
    explicit aliases in the vocabulary table instead, where each one is a
    deliberate, reviewable decision rather than a side effect of a regex.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    lowered = without_marks.replace("ß", "ss").lower()
    return _WHITESPACE_RUN.sub(" ", lowered).strip()


@dataclass(frozen=True)
class StateVocabulary:
    """
    One country's canonical first-level region names and their aliases.

    Built by the repository from the `country_states` table and then treated as
    immutable data, so matching needs no further I/O.
    """

    country_code: str
    entries: dict  # folded alias/canonical key -> canonical display name

    @classmethod
    def from_rows(
        cls, country_code: str, names: Iterable[str], aliases: Iterable[Iterable[str]]
    ) -> "StateVocabulary":
        """
        Build the lookup from parallel name/alias sequences.

        Indexed rather than `zip`ped: a missing alias group must not silently
        truncate the vocabulary, because an empty vocabulary degrades to
        pass-through and would quietly stop normalising that country.
        """
        names = list(names)
        alias_groups = list(aliases)
        entries: dict = {}
        for index, name in enumerate(names):
            entries[fold(name)] = name
            group = alias_groups[index] if index < len(alias_groups) else ()
            for alias in group or ():
                # setdefault: the canonical name always wins over an alias that
                # happens to fold onto it.
                entries.setdefault(fold(alias), name)
        return cls(country_code=country_code.upper(), entries=entries)

    def canonical(self, value: str) -> Optional[str]:
        """Canonical name for an input spelling, or None if not in the vocabulary."""
        return self.entries.get(fold(value))

    def names(self) -> list:
        """Canonical names in the vocabulary, deduplicated and sorted."""
        return sorted(set(self.entries.values()))

    def __len__(self) -> int:
        return len(self.entries)


def resolve_state(
    country_code: Optional[str],
    value: Optional[str],
    vocabulary_for,
) -> Optional[str]:
    """
    Canonicalise `state` for the given country.

    `vocabulary_for(country_code) -> Optional[StateVocabulary]` is injected so
    this stays testable and so the lookup is lazy: countries without a
    vocabulary never cost a query.

    Behaviour:
      * no country, or a country with no vocabulary -> trimmed free text. We do
        not know what a "state" means there, so inventing a rule would be worse
        than storing what the admin typed.
      * country has a vocabulary and the value matches (or is already
        canonical) -> the canonical name, so "Hesse", "hessen" and "Hessen" all
        store as "Hessen".
      * country has a vocabulary and the value does not match -> rejected.

    The rejection is the one place this is strict. It is what actually prevents
    the column from fragmenting: an unknown spelling for a country whose full
    region list we hold would otherwise be stored as a second canonical value,
    and every later filter on that region would silently miss it. Countries we
    know nothing about are unaffected, because they have no vocabulary to
    contradict.
    """
    cleaned = clean_state(value)
    if cleaned is None:
        return None

    if not country_code:
        return cleaned

    vocabulary = vocabulary_for(country_code)
    if vocabulary is None or not len(vocabulary):
        # No vocabulary for this country: pass through, never guess.
        return cleaned

    canonical = vocabulary.canonical(cleaned)
    if canonical is not None:
        return canonical

    raise ServiceError(
        "INVALID_INPUT",
        f"{cleaned!r} is not a known first-level region for {country_code}. "
        "Use one of: " + ", ".join(vocabulary.names()),
        422,
    )