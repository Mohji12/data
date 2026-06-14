from app.services.whatsapp import (
    SendResult,
    normalize_phone,
    send_bulk_template,
    send_bulk_text,
    split_batches,
)


def test_normalize_phone_accepts_indian_10_digit():
    assert normalize_phone("98765 43210") == "+919876543210"


def test_normalize_phone_rejects_invalid():
    try:
        normalize_phone("abc")
        assert False, "Expected ValueError for invalid phone"
    except ValueError:
        assert True


def test_split_batches_chunks_items():
    chunks = split_batches([1, 2, 3, 4, 5], 2)
    assert chunks == [[1, 2], [3, 4], [5]]


def test_send_bulk_text_dedupes_and_aggregates(monkeypatch):
    calls: list[str] = []

    def fake_send(phone: str, message: str):
        calls.append(phone)
        if phone.endswith("11"):
            return SendResult(phone=phone, success=False, error="bad number", status_code=400)
        return SendResult(phone=phone, success=True, provider_message_id="wamid.1", status_code=200)

    monkeypatch.setattr("app.services.whatsapp.send_whatsapp_text", fake_send)

    out = send_bulk_text(["+919999999999", "+919999999999", "+911111111111"], "hello")
    assert out["total"] == 2
    assert out["sent"] == 1
    assert out["failed"] == 1
    assert len(calls) == 2


def test_send_bulk_template_aggregates(monkeypatch):
    calls: list[str] = []

    def fake_send(phone: str, template_name: str, language_code: str, body_params=None):
        calls.append(phone)
        return SendResult(phone=phone, success=True, provider_message_id="wamid.t", status_code=200)

    monkeypatch.setattr("app.services.whatsapp.send_whatsapp_template", fake_send)

    out = send_bulk_template(["+919999999999"], "hello_world", "en")
    assert out["total"] == 1
    assert out["sent"] == 1
    assert calls == ["+919999999999"]
