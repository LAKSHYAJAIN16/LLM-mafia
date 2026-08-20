import json

import requests

from mafia_sim.providers.openai_compat_provider import OpenAICompatProvider

# Built from chr() codepoints (not literal characters or \u escape source text)
# because both were observed to get silently mangled somewhere in this
# environment's own tool-call pipeline before ever reaching this file --
# chr() is pure ASCII digits, so it's immune to that.
EM_DASH_TEXT = "already" + chr(8212) + "let" + chr(8217) + "s hear more"
REPLACEMENT_CHAR = chr(0xFFFD)


class _FakeResponse:
    """Minimal stand-in for requests.Response: only .status_code and .content
    are touched by our provider code (never .text/.json(), which is the point --
    those go through requests' own encoding guess, which is what corrupted
    multi-byte characters like em dashes into U+FFFD in production).
    """

    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content


def test_complete_decodes_utf8_body_correctly(monkeypatch):
    # ensure_ascii=False on both dumps calls matters: real API responses put raw
    # multi-byte UTF-8 characters on the wire, not pre-escaped \uXXXX ASCII text.
    # Using the (accidental) default ensure_ascii=True here would pre-escape the
    # em dash before it ever becomes a byte, making this test unable to exercise
    # the corruption path at all.
    inner_content = json.dumps({"thought": "x", "message": EM_DASH_TEXT}, ensure_ascii=False)
    payload = {
        "choices": [{"message": {"content": inner_content}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(200, body_bytes)

    monkeypatch.setattr(requests, "post", fake_post)

    provider = OpenAICompatProvider("some-model", "fake-key", "https://example.com/v1")
    resp = provider.complete("system", "user")

    assert resp.error is None
    assert EM_DASH_TEXT in resp.text
    assert REPLACEMENT_CHAR not in resp.text  # no replacement-character corruption


def test_complete_flags_a_completely_empty_message_as_an_error(monkeypatch):
    # Observed in production with GLM-4.6 via OpenRouter: HTTP 200, well-formed
    # response shape, but message.content is "" -- most likely its entire max_tokens
    # budget was consumed by invisible reasoning tokens. This should surface as an
    # error rather than a silent "successful" empty response.
    payload = {"choices": [{"message": {"content": ""}}], "usage": {"prompt_tokens": 500, "completion_tokens": 500}}
    body_bytes = json.dumps(payload).encode("utf-8")

    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResponse(200, body_bytes)

    monkeypatch.setattr(requests, "post", fake_post)

    provider = OpenAICompatProvider("some-model", "fake-key", "https://example.com/v1")
    resp = provider.complete("system", "user")

    assert resp.error == "empty_completion"
    assert resp.text == ""
