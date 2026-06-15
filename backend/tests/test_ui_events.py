from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.routers.ui_events import (
    _clean_label,
    _mask_path,
    _payload_from_event,
    _sanitize_detail,
)
from app.schemas import UI_EVENT_BATCH_MAX_EVENTS, UiEventBatchIn, UiEventIn
from app.services.ui_event_pg import UiEventPayload, _ui_event_insert_params


def test_mask_path_reduces_identifiers_and_query_to_keys() -> None:
    masked = _mask_path(
        "/families/3fa85f64-5717-4562-b3fc-2c963f66afa6/small-variants?gene=BRCA1&clinvar=path"
    )
    assert masked == "/families/:id/small-variants?clinvar&gene"


def test_mask_path_masks_numeric_id_segments() -> None:
    assert _mask_path("/projects/12345/page/2") == "/projects/:id/page/2"


def test_clean_label_collapses_whitespace_and_truncates() -> None:
    assert _clean_label("  Apply\n  filters  ") == "Apply filters"
    assert len(_clean_label("x" * 500) or "") == 200


def test_sanitize_detail_masks_sensitive_keys() -> None:
    sanitized = _sanitize_detail({"token": "abc", "count": 3, "label": "ok"})
    assert sanitized["token"] == "***"
    assert sanitized["count"] == 3
    assert sanitized["label"] == "ok"


def test_payload_takes_actor_from_user_not_body_and_drops_unknown_type() -> None:
    user = SimpleNamespace(id="u-1", email="analyst@example.com", role="viewer")

    rejected = _payload_from_event(
        UiEventIn(event_type="exfiltrate"),
        user=user,
        remote_ip="127.0.0.1",
        user_agent="pytest",
    )
    assert rejected is None

    payload = _payload_from_event(
        UiEventIn(
            event_type="click",
            category="button",
            label="Save preset",
            to_path="/families/3fa85f64-5717-4562-b3fc-2c963f66afa6/small-variants",
        ),
        user=user,
        remote_ip="127.0.0.1",
        user_agent="pytest",
    )
    assert payload is not None
    assert payload.event_type == "click"
    assert payload.user_email == "analyst@example.com"
    assert payload.user_role == "viewer"
    assert payload.to_path == "/families/:id/small-variants"


def test_event_batch_accepts_up_to_the_cap() -> None:
    batch = UiEventBatchIn(
        events=[UiEventIn(event_type="click")] * UI_EVENT_BATCH_MAX_EVENTS
    )
    assert len(batch.events) == UI_EVENT_BATCH_MAX_EVENTS


def test_event_batch_rejects_oversize_batch() -> None:
    # An over-cap batch is now an explicit validation error (HTTP 422 at the
    # route) rather than a silently truncated 202.
    with pytest.raises(ValidationError):
        UiEventBatchIn(
            events=[UiEventIn(event_type="click")] * (UI_EVENT_BATCH_MAX_EVENTS + 1)
        )


def test_insert_params_serializes_detail_to_json_string() -> None:
    params = _ui_event_insert_params(
        UiEventPayload(event_type="navigation", detail={"from": "/a", "to": "/b"})
    )
    assert isinstance(params["detail"], str)
    assert params["detail"] == '{"from": "/a", "to": "/b"}'
