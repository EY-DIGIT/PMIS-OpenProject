"""Pure-helper tests for ``app/shared/code_generators.py`` (doc 25)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, MetaData, String, Table, create_engine, text

from app.shared.code_generators import (
    IST,
    SLUG_LENGTH,
    build_code,
    generate_unique_code,
    ist_timestamp,
    looks_like_user_code,
    looks_like_vendor_code,
    slug4,
)


# ===========================================================================
# slug4
# ===========================================================================

class TestSlug4:
    @pytest.mark.parametrize("source,expected", [
        # Long-enough sources are truncated at SLUG_LENGTH (4).
        ("Acme Corp", "ACME"),
        ("Acme Corporation Pvt Ltd", "ACME"),
        ("acme", "ACME"),
        ("3M India", "3MIN"),
        ("AT&T Inc", "ATTI"),
        ("MIDA", "MIDA"),
        # Variable-length cases: shorter sources keep their natural
        # length (no filler digits like "Z000"). Resolves the
        # "VN-FSV0-..." cosmetic bug from doc 25.
        ("Z", "Z"),
        ("xy", "XY"),
        ("a-b", "AB"),
        ("fsv", "FSV"),
        # Special-only / empty / None still fall back to all zeros —
        # the slug must never be the empty string (would produce
        # ``VN--260502143015`` and break ``-``-based parsing).
        ("....", "0000"),
        ("", "0000"),
        (None, "0000"),
        # Unicode passes through stripping (anything non-[A-Z0-9] is
        # discarded, regardless of script).
        ("àéé Brand", "BRAN"),
        # Truncated when longer than SLUG_LENGTH.
        ("AABBCCDDEEFF", "AABB"),
    ])
    def test_slug4(self, source, expected):
        out = slug4(source)
        assert out == expected
        # Length is now variable (1..SLUG_LENGTH for non-empty alphanumeric
        # sources; SLUG_LENGTH for the all-zero fallback).
        assert 1 <= len(out) <= SLUG_LENGTH


# ===========================================================================
# ist_timestamp
# ===========================================================================

class TestIstTimestamp:
    def test_utc_input_converted_to_ist(self):
        # 2026-05-02 09:00:15 UTC == 2026-05-02 14:30:15 IST
        utc = datetime(2026, 5, 2, 9, 0, 15, tzinfo=timezone.utc)
        assert ist_timestamp(utc) == "260502143015"

    def test_naive_input_assumed_utc(self):
        # Naive datetime is treated as UTC then converted to IST.
        naive = datetime(2026, 5, 2, 9, 0, 15)
        assert ist_timestamp(naive) == "260502143015"

    def test_already_ist_input_round_trips(self):
        ist_dt = datetime(2026, 5, 2, 14, 30, 15, tzinfo=IST)
        assert ist_timestamp(ist_dt) == "260502143015"

    def test_string_input_iso_with_microseconds(self):
        # SQLite returns DATETIME columns as strings via raw SQL —
        # the alembic backfill must tolerate that without a manual cast.
        assert ist_timestamp("2026-05-02 09:00:15.000000") == "260502143015"

    def test_string_input_iso_no_microseconds(self):
        assert ist_timestamp("2026-05-02 09:00:15") == "260502143015"

    def test_string_input_with_z_suffix(self):
        assert ist_timestamp("2026-05-02T09:00:15Z") == "260502143015"

    def test_output_length_always_12(self):
        for d in (
            datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            datetime(2099, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
            datetime(2026, 5, 2, tzinfo=timezone.utc),
        ):
            assert len(ist_timestamp(d)) == 12


# ===========================================================================
# build_code
# ===========================================================================

class TestBuildCode:
    def test_typical_vendor(self):
        when = datetime(2026, 5, 2, 9, 0, 15, tzinfo=timezone.utc)
        assert build_code("VN", "Acme Corp", when) == "VN-ACME-260502143015"

    def test_typical_user(self):
        when = datetime(2026, 5, 2, 9, 0, 15, tzinfo=timezone.utc)
        assert build_code("US", "admin", when) == "US-ADMI-260502143015"

    def test_short_source_kept_natural_length(self):
        """Variable-length slug — shorter sources are NOT padded with
        zeros (resolves the ``VN-FSV0-...`` cosmetic bug)."""
        when = datetime(2026, 5, 2, 9, 0, 15, tzinfo=timezone.utc)
        assert build_code("US", "z", when) == "US-Z-260502143015"
        assert build_code("VN", "fsv", when) == "VN-FSV-260502143015"
        assert build_code("VN", "xy", when) == "VN-XY-260502143015"

    def test_empty_source_falls_back_to_zeros(self):
        when = datetime(2026, 5, 2, 9, 0, 15, tzinfo=timezone.utc)
        assert build_code("VN", "....", when) == "VN-0000-260502143015"
        assert build_code("VN", None, when) == "VN-0000-260502143015"

    def test_total_length_for_4char_source(self):
        when = datetime(2026, 5, 2, 9, 0, 15, tzinfo=timezone.utc)
        # "{prefix}-{4}-{12}" with prefix VN/US (2 chars) → 2+1+4+1+12 = 20
        assert len(build_code("VN", "ACME", when)) == 20
        assert len(build_code("US", "JOHN", when)) == 20

    def test_total_length_varies_for_short_sources(self):
        """Codes are no longer fixed-length now that the slug is
        variable. Lookups split on ``-``, so shorter codes parse fine."""
        when = datetime(2026, 5, 2, 9, 0, 15, tzinfo=timezone.utc)
        # "VN-Z-260502143015" → 2+1+1+1+12 = 17
        assert len(build_code("VN", "Z", when)) == 17
        # "VN-FSV-260502143015" → 2+1+3+1+12 = 19
        assert len(build_code("VN", "FSV", when)) == 19


# ===========================================================================
# generate_unique_code — collision suffixing against a real SQLite table
# ===========================================================================

@pytest.fixture()
def unique_engine():
    """Tiny in-memory SQLite + a single ``things`` table with a code column.
    Used to exercise the collision logic against a real connection."""
    engine = create_engine("sqlite:///:memory:")
    md = MetaData()
    Table(
        "things", md,
        Column("id", String(36), primary_key=True),
        Column("code", String(50), unique=True),
    )
    md.create_all(engine)
    yield engine
    engine.dispose()


def _seed_codes(engine, codes):
    with engine.begin() as conn:
        for i, code in enumerate(codes):
            conn.execute(
                text("INSERT INTO things (id, code) VALUES (:id, :c)"),
                {"id": f"id-{i}", "c": code},
            )


class TestGenerateUniqueCode:
    def test_no_collision_returns_base(self, unique_engine):
        with unique_engine.begin() as conn:
            out = generate_unique_code(
                conn, table="things", code_column="code",
                base_code="VN-ACME-260502143015",
            )
        assert out == "VN-ACME-260502143015"

    def test_one_collision_appends_2(self, unique_engine):
        _seed_codes(unique_engine, ["VN-ACME-260502143015"])
        with unique_engine.begin() as conn:
            out = generate_unique_code(
                conn, table="things", code_column="code",
                base_code="VN-ACME-260502143015",
            )
        assert out == "VN-ACME-260502143015-2"

    def test_chain_of_collisions(self, unique_engine):
        _seed_codes(unique_engine, [
            "VN-ACME-260502143015",
            "VN-ACME-260502143015-2",
            "VN-ACME-260502143015-3",
        ])
        with unique_engine.begin() as conn:
            out = generate_unique_code(
                conn, table="things", code_column="code",
                base_code="VN-ACME-260502143015",
            )
        assert out == "VN-ACME-260502143015-4"

    def test_exclude_id_lets_a_row_keep_its_own_code(self, unique_engine):
        """Backfill re-run scenario: a row already has the base code; we
        want to allow it to keep that code without seeing itself as a
        collision."""
        _seed_codes(unique_engine, ["VN-ACME-260502143015"])
        with unique_engine.begin() as conn:
            out = generate_unique_code(
                conn, table="things", code_column="code",
                base_code="VN-ACME-260502143015",
                exclude_id="id-0",
            )
        assert out == "VN-ACME-260502143015"


# ===========================================================================
# Recognizers
# ===========================================================================

class TestRecognizers:
    @pytest.mark.parametrize("s", [
        "VN-ACME-260502143015",
        "VN-ACME-260502143015-2",
        "VN-0000-260502143015",
    ])
    def test_looks_like_vendor_code_true(self, s):
        assert looks_like_vendor_code(s) is True

    @pytest.mark.parametrize("s", [
        "8bd99f06-5f2a-424c-aaff-10ab163c3e42",  # UUID
        "vendorname",
        "vn-acme-...",                            # case-sensitive prefix
        "",
        None,
        123,
    ])
    def test_looks_like_vendor_code_false(self, s):
        assert looks_like_vendor_code(s) is False

    @pytest.mark.parametrize("s", [
        "US-ADMI-260101000000",
        "US-JOHN-260502143015-3",
    ])
    def test_looks_like_user_code_true(self, s):
        assert looks_like_user_code(s) is True

    @pytest.mark.parametrize("s", [
        "5",
        "1",
        "us-admi-...",
        "",
        None,
        5,   # int → False; caller handles int separately
    ])
    def test_looks_like_user_code_false(self, s):
        assert looks_like_user_code(s) is False
