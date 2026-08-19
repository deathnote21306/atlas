"""pgvector returns embeddings as a string, so dedup must accept both forms.

Regression guard: passing the string form used to be iterated character by
character, producing "[[,-,0,.,0,5,..." and a DataError that aborted the whole
news pipeline run.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from atlas_api.services.news.semantic_dedup import find_near_duplicates


def _session_capturing_params() -> tuple[MagicMock, dict]:
    captured: dict = {}
    session = MagicMock()

    def execute(_stmt, params):
        captured.update(params)
        result = MagicMock()
        result.fetchall.return_value = []
        return result

    session.execute.side_effect = execute
    return session, captured


def test_accepts_a_float_list():
    session, captured = _session_capturing_params()
    find_near_duplicates(session, uuid.uuid4(), [0.1, -0.2, 0.3])
    assert captured["vec"] == "[0.1,-0.2,0.3]"


def test_accepts_the_pgvector_string_form_unchanged():
    session, captured = _session_capturing_params()
    find_near_duplicates(session, uuid.uuid4(), "[0.1,-0.2,0.3]")
    assert captured["vec"] == "[0.1,-0.2,0.3]"


def test_string_form_is_not_exploded_into_characters():
    session, captured = _session_capturing_params()
    find_near_duplicates(session, uuid.uuid4(), "[0.1,-0.2]")
    assert ",-," not in captured["vec"], "string was iterated character by character"
