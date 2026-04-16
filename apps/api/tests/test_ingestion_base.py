from atlas_api.ingestion.circuit_breaker import (
    FAILURE_THRESHOLD,
    is_open,
    record_failure,
    record_success,
    reset,
)


def test_circuit_starts_closed(session):
    assert is_open(session, "worldbank") is False


def test_circuit_opens_after_threshold_failures(session):
    for _ in range(FAILURE_THRESHOLD - 1):
        record_failure(session, "worldbank")
    assert is_open(session, "worldbank") is False
    record_failure(session, "worldbank")
    assert is_open(session, "worldbank") is True


def test_success_resets_failures(session):
    record_failure(session, "imf_weo")
    record_failure(session, "imf_weo")
    record_success(session, "imf_weo")
    assert is_open(session, "imf_weo") is False
    # Needs 3 fresh failures to open again
    record_failure(session, "imf_weo")
    assert is_open(session, "imf_weo") is False


def test_manual_reset(session):
    for _ in range(FAILURE_THRESHOLD):
        record_failure(session, "fx")
    assert is_open(session, "fx") is True
    reset(session, "fx")
    assert is_open(session, "fx") is False
