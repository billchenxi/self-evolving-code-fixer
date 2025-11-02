import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("FIRECRAWL_API_KEY"), reason="FIRECRAWL_API_KEY not set"
)


def _as_markdown(doc) -> str:
    # Firecrawl returns a Document model; fall back to dict for older clients.
    if hasattr(doc, "markdown"):
        return doc.markdown or ""
    if isinstance(doc, dict):
        return doc.get("markdown", "") or ""
    return ""


def test_firecrawl_client_can_fetch_markdown():
    from firecrawl import Firecrawl

    client = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    out = client.scrape(
        "https://docs.python.org/3/tutorial/index.html", formats=["markdown"]
    )
    md = _as_markdown(out)
    assert isinstance(md, str) and len(md) > 50


def test_web_hints_returns_snippet_for_nonetype():
    from agent.planner import _web_hints

    fake_log = "TypeError: 'NoneType' object is not subscriptable"
    snippet = _web_hints(fake_log)
    assert isinstance(snippet, str)
    assert "Source:" in snippet and len(snippet) > 50
