from atlas_schemas.health import HealthResponse


def test_health_response_roundtrips():
    payload = {"status": "ok", "version": "0.0.0"}
    obj = HealthResponse.model_validate(payload)
    assert obj.status == "ok"
    assert obj.version == "0.0.0"
    assert obj.model_dump() == payload


def test_health_response_rejects_unknown_status():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        HealthResponse.model_validate({"status": "bogus", "version": "0.0.0"})
