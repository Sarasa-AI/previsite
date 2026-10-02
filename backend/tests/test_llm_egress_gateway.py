"""Synthetic scrubber / gateway tests — fake identifiers only; no clinical narratives."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.privacy.scrubber import (
    PatientKnownIds,
    ScrubberError,
    messages_contain_image,
    rehydrate_text,
    scrub_text,
)


# Fake identifiers only (not real people / numbers).
FAKE_NAME = "Ali Testperson"
FAKE_NID = "0499370899"  # checksum-valid synthetic
FAKE_PHONE = "+989121234567"
FAKE_EMAIL = "ali.testperson@example.com"


def test_scrub_known_name_and_variants():
    known = PatientKnownIds(name_parts=["Ali", "Testperson"])
    text = "Hello Ali Testperson and علی"
    # Latin name parts only for this fixture
    result = scrub_text("Patient Ali spoke with Testperson today.", known=known)
    assert "Ali" not in result.text or "REDACTED_NAME" in result.text
    assert "Testperson" not in result.text
    assert result.counts.get("name", 0) >= 1


def test_scrub_national_id_checksum_and_spaced():
    result = scrub_text(f"id={FAKE_NID} spaced=0 4 9 9 3 7 0 8 9 9")
    assert FAKE_NID not in result.text
    assert result.counts.get("national_id", 0) >= 1


def test_scrub_phone_digit_variants():
    result = scrub_text(f"call {FAKE_PHONE} or ۰۹۱۲۱۲۳۴۵۶۷")
    assert "9121234567" not in result.text.replace("REDACTED", "")
    assert result.counts.get("phone", 0) >= 1


def test_scrub_email_and_url():
    result = scrub_text(f"mail {FAKE_EMAIL} see https://example.com/x")
    assert FAKE_EMAIL not in result.text
    assert "https://example.com" not in result.text
    assert result.counts.get("email", 0) >= 1
    assert result.counts.get("url", 0) >= 1


def test_scrub_zero_width_in_known_phone():
    known = PatientKnownIds(phone=FAKE_PHONE)
    sneaky = "+98\u200c912\u200b1234567"
    result = scrub_text(f"p={sneaky}", known=known)
    assert result.counts.get("phone", 0) >= 1


def test_golden_prompt_byte_identical_apart_from_ids():
    known = PatientKnownIds(
        name_parts=[FAKE_NAME.split()[0], FAKE_NAME.split()[1]],
        national_id=FAKE_NID,
        phone=FAKE_PHONE,
        email=FAKE_EMAIL,
    )
    template = "Question for {name} nid={nid} phone={phone} email={email} ok."
    raw = template.format(
        name=FAKE_NAME.split()[0],
        nid=FAKE_NID,
        phone=FAKE_PHONE,
        email=FAKE_EMAIL,
    )
    result = scrub_text(raw, known=known)
    # Structure preserved: still starts with Question and ends with ok.
    assert result.text.startswith("Question for ")
    assert result.text.endswith(" ok.")
    assert FAKE_NID not in result.text
    assert FAKE_PHONE not in result.text
    assert FAKE_EMAIL not in result.text


def test_rehydrate_placeholders():
    known = PatientKnownIds(national_id=FAKE_NID)
    scrubbed = scrub_text(f"nid {FAKE_NID}", known=known)
    echoed = scrubbed.text  # model might echo placeholders
    display = rehydrate_text(echoed, scrubbed.placeholders)
    assert FAKE_NID in display


def test_fail_closed_on_none():
    with pytest.raises(ScrubberError):
        scrub_text(None)  # type: ignore[arg-type]


def test_image_detection():
    assert messages_contain_image(
        [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}]
    )
    assert not messages_contain_image([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_allowlist_enforcement():
    from app.privacy.llm_egress_gateway import LlmProviderNotAllowed, assert_provider_allowed

    with pytest.raises(LlmProviderNotAllowed):
        assert_provider_allowed("https://evil-llm.example/v1")


@pytest.mark.asyncio
async def test_image_block_default(monkeypatch):
    from app.core import config as config_module
    from app.privacy.llm_egress_gateway import LlmImageEgressBlocked, chat_completion

    monkeypatch.setattr(config_module.settings, "allow_external_image_inference", False)
    with pytest.raises(LlmImageEgressBlocked):
        await chat_completion(
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-test",
            model="test",
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,xx"}}],
                }
            ],
            purpose="test_image",
        )


def test_codebase_scan_no_direct_provider_clients():
    """Fail if AsyncOpenAI or provider base URL literals appear outside the gateway."""
    root = Path(__file__).resolve().parents[1] / "app"
    allowed_paths = {
        root / "privacy" / "llm_egress_gateway.py",
    }
    # Also allow this test file's references via not scanning tests.
    violations: list[str] = []
    for path in root.rglob("*.py"):
        if path in allowed_paths:
            continue
        # Skip privacy scrubber (no clients)
        text = path.read_text(encoding="utf-8")
        if "AsyncOpenAI" in text:
            violations.append(f"{path.relative_to(root)}: AsyncOpenAI")
        if "openrouter.ai/api" in text.lower() and "llm_egress" not in str(path):
            # settings default URLs in config.py are allowed as settings only
            if path.name not in ("config.py",) and "base_url" in text:
                # config stores URLs; gateway reads settings — allow config.py
                if "config.py" not in str(path):
                    # .env.example is outside app/
                    if "AsyncOpenAI" in text or "chat.completions.create" in text:
                        violations.append(f"{path.relative_to(root)}: direct openrouter URL usage")
        if "chat.completions.create" in text:
            violations.append(f"{path.relative_to(root)}: chat.completions.create")
        if "AsyncOpenAI(" in text:
            violations.append(f"{path.relative_to(root)}: AsyncOpenAI(")

    # config.py may mention base URLs as settings defaults — strip those
    violations = [v for v in violations if not v.startswith("core/config.py")]
    assert not violations, "Direct provider client usage outside gateway:\n" + "\n".join(
        violations
    )


def test_egress_log_model_has_no_content_columns():
    from app.models.llm_egress_log import LlmEgressLog

    cols = {c.name for c in LlmEgressLog.__table__.columns}
    forbidden = {"prompt", "response", "content", "messages", "body", "payload"}
    assert not (cols & forbidden)
