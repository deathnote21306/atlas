"""The tool schema handed to Claude must be self-contained.

Regression guard: _pydantic_to_tool_schema previously forwarded only
properties and required, dropping $defs. Any model with an enum or a nested
model then produced a dangling $ref that Claude could not resolve, so it
invented values and adjacent fields came back malformed.
"""

from __future__ import annotations

from atlas_api.services.ai.provider import _pydantic_to_tool_schema
from atlas_schemas.ai import NewsGradeResult, SynopsisContent


def _refs(node) -> list[str]:
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str):
                found.append(v)
            else:
                found.extend(_refs(v))
    elif isinstance(node, list):
        for v in node:
            found.extend(_refs(v))
    return found


def test_enum_refs_are_resolvable_for_the_news_grader():
    tool = _pydantic_to_tool_schema("grade", "d", NewsGradeResult)
    schema = tool["input_schema"]
    refs = _refs(schema)
    assert refs, "expected event_type to use a $ref"
    defs = schema.get("$defs", {})
    for ref in refs:
        name = ref.split("/")[-1]
        assert name in defs, f"dangling $ref {ref}: $defs was dropped"


def test_nested_model_refs_are_resolvable_for_synopsis():
    tool = _pydantic_to_tool_schema("syn", "d", SynopsisContent)
    schema = tool["input_schema"]
    defs = schema.get("$defs", {})
    for ref in _refs(schema):
        assert ref.split("/")[-1] in defs, f"dangling $ref {ref}"


def test_event_type_enum_values_reach_the_model():
    tool = _pydantic_to_tool_schema("grade", "d", NewsGradeResult)
    blob = str(tool["input_schema"])
    for value in ("Monetary", "Fiscal", "Rating", "IMF", "Market"):
        assert value in blob, f"{value} missing from the tool schema"
