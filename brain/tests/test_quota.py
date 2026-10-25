import pytest
from google.genai import errors

from brain.llm.client import LLMClient, QuotaExhausted, quota_info

# Shapes copied from a real free-tier 429 (trimmed).
DAILY = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota exceeded", "details": [
    {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
        {"quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
         "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "35786s"}]}}
PER_MINUTE = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "slow down", "details": [
    {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
        {"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "0s"}]}}


def test_quota_info_tells_daily_from_per_minute():
    assert quota_info(DAILY) == (True, 35786.0)
    assert quota_info(PER_MINUTE) == (False, 0.0)


class _Models:
    def __init__(self, failures):
        self.failures, self.calls = failures, 0

    def generate_content(self, **_):
        self.calls += 1
        if self.failures:
            raise errors.APIError(429, self.failures.pop(0))
        return "ok"


def _client(failures):
    llm = LLMClient("test-key", "gemini-3.8-flash")
    llm._client = type("C", (), {"models": _Models(failures)})()
    return llm


def test_daily_quota_fails_fast_without_retrying():
    llm = _client([DAILY])
    with pytest.raises(QuotaExhausted) as e:
        llm._call("prompt", None)
    assert llm._client.models.calls == 1 and "9.9h" in str(e.value)


def test_per_minute_limit_is_retried(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    llm = _client([PER_MINUTE, PER_MINUTE])
    assert llm._call("prompt", None) == "ok" and llm._client.models.calls == 3
