import os, requests
from urllib.parse import urlparse
from .db import get_state, set_state

API = "https://api.telegram.org/bot"


def send(text, keyboard=None):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]
    payload = {"chat_id": chat, "text": text, "disable_web_page_preview": True}
    if keyboard:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    r = requests.post(f"{API}{token}/sendMessage", json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def _valid_http_url(value):
    if not isinstance(value, str):
        return False
    value = value.strip()
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def callback_button_row(oid, application_url=None):
    # Telegram requires an absolute HTTP(S) URL for URL buttons. AI extraction
    # may return placeholders such as "Not stated", so never pass those through.
    apply_button = {"text": "🔗 Apply", "callback_data": f"apply:{oid}"}
    if _valid_http_url(application_url):
        apply_button = {"text": "🔗 Apply", "url": application_url.strip()}
    return [[
        apply_button,
        {"text": "💾 Save", "callback_data": f"save:{oid}"},
        {"text": "🚫 Ignore", "callback_data": f"ignore:{oid}"}
    ], [
        {"text": "✅ Applied", "callback_data": f"applied:{oid}"}
    ]]


def poll_once():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    last_id = int(get_state("telegram_last_update_id", "0"))
    params = {"timeout": 5, "offset": last_id + 1}
    r = requests.get(f"{API}{token}/getUpdates", params=params, timeout=15)
    r.raise_for_status()
    updates = r.json().get("result", [])
    if updates:
        set_state("telegram_last_update_id", max(u["update_id"] for u in updates))
    return updates


def acknowledge(callback_id, message):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    requests.post(
        f"{API}{token}/answerCallbackQuery",
        json={"callback_query_id": callback_id, "text": message},
        timeout=10
    )
