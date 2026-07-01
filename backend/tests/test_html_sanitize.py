from __future__ import annotations

from backend.app.core.html_sanitize import sanitize_reference_html


def test_none_and_empty_pass_through() -> None:
    assert sanitize_reference_html(None) is None
    assert sanitize_reference_html("") == ""
    assert sanitize_reference_html("   ") == "   "


def test_script_tag_is_removed_but_text_is_kept_as_inert_text() -> None:
    out = sanitize_reference_html("<b>Gene</b><script>alert(1)</script>")
    assert "<script>" not in out
    assert "<b>Gene</b>" in out
    # The script's text survives only as inert text, never as an executable element.
    assert "alert(1)" in out


def test_event_handler_and_image_payload_removed() -> None:
    out = sanitize_reference_html('<img src=x onerror="alert(1)">hello')
    assert "<img" not in out
    assert "onerror" not in out
    assert "hello" in out


def test_javascript_href_scheme_is_stripped_but_anchor_text_kept() -> None:
    out = sanitize_reference_html('<a href="javascript:alert(1)">click</a>')
    assert "javascript" not in out.lower()
    assert ">click</a>" in out


def test_safe_href_and_allowlisted_formatting_preserved() -> None:
    src = '<p>See <a href="https://omim.org/entry/1" title="OMIM">OMIM</a><br/><em>note</em></p>'
    out = sanitize_reference_html(src)
    assert 'href="https://omim.org/entry/1"' in out
    assert 'title="OMIM"' in out
    assert "<em>note</em>" in out
    assert "<br" in out


def test_disallowed_attributes_are_dropped_from_allowed_tags() -> None:
    out = sanitize_reference_html('<p class="x" style="color:red" onclick="x()">t</p>')
    assert "class" not in out
    assert "style" not in out
    assert "onclick" not in out
    assert ">t</p>" in out
