import json
from email.message import Message
from io import BytesIO
from types import SimpleNamespace

from agent.tools.web import _TextExtractor, _validate_public_url, read_webpage, search_web


def test_search_web_requires_api_key(monkeypatch: object) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)  # type: ignore[attr-defined]

    result = search_web("latest Python release")

    assert result.success is False
    assert "BRAVE_SEARCH_API_KEY" in (result.error or "")


def test_search_web_returns_bounded_source_results(monkeypatch: object) -> None:
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "test-key")  # type: ignore[attr-defined]

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            return json.dumps({"web": {"results": [
                {"title": "A title", "url": "https://example.com", "description": "A result"}
            ]}}).encode()

    monkeypatch.setattr("agent.tools.web.build_opener", lambda: SimpleNamespace(open=lambda *a, **k: FakeResponse()))  # type: ignore[attr-defined]

    result = search_web("query")

    assert result.success is True
    assert json.loads(result.data)["results"][0]["url"] == "https://example.com"


def test_public_url_validation_rejects_local_and_private_networks(monkeypatch: object) -> None:
    assert _validate_public_url("file:///etc/passwd") is not None
    assert _validate_public_url("http://127.0.0.1/") is not None
    assert _validate_public_url("http://localhost/") is not None

    monkeypatch.setattr("agent.tools.web.socket.getaddrinfo", lambda *a: [  # type: ignore[attr-defined]
        (0, 0, 0, "", ("10.0.0.2", 0))
    ])
    assert _validate_public_url("http://private.example/") is not None


def test_text_extractor_skips_script_and_extracts_title() -> None:
    parser = _TextExtractor()
    parser.feed("<title>Example</title><p>Hello</p><script>ignore this</script>")

    assert " ".join(parser.title_parts) == "Example"
    assert "Hello" in " ".join(parser.parts)
    assert "ignore this" not in " ".join(parser.parts)


def test_read_webpage_rejects_local_url_without_network() -> None:
    result = read_webpage("http://127.0.0.1/")

    assert result.success is False
    assert "públicos" in (result.error or "")
