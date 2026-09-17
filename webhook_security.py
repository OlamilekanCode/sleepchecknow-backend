import base64
import hashlib
import hmac
import os
import time


WEBFLOW_WEBHOOK_SECRET = os.environ.get(
    "WEBFLOW_WEBHOOK_SECRET",
    ""
)

MAX_WEBHOOK_AGE_MS = 5 * 60 * 1000


def get_headers(event):
    headers = event.get("headers") or {}

    return {
        str(key).lower(): value
        for key, value in headers.items()
    }


def get_raw_body(event):
    body = event.get("body", "")

    if body is None:
        return ""

    if event.get("isBase64Encoded"):
        decoded = base64.b64decode(body)
        return decoded.decode("utf-8")

    if isinstance(body, str):
        return body

    return str(body)


def verify_webflow_signature(event):
    if not WEBFLOW_WEBHOOK_SECRET:
        return False

    headers = get_headers(event)

    timestamp = headers.get("x-webflow-timestamp")
    provided_signature = headers.get(
        "x-webflow-signature"
    )

    if not timestamp or not provided_signature:
        return False

    try:
        request_timestamp = int(timestamp)
    except (TypeError, ValueError):
        return False

    current_timestamp = int(time.time() * 1000)

    # Reject old/replayed requests and unrealistic future requests
    if abs(
        current_timestamp - request_timestamp
    ) > MAX_WEBHOOK_AGE_MS:
        return False

    raw_body = get_raw_body(event)

    signed_content = (
        f"{timestamp}:{raw_body}"
    )

    expected_signature = hmac.new(
        WEBFLOW_WEBHOOK_SECRET.encode("utf-8"),
        signed_content.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected_signature.lower(),
        str(provided_signature).strip().lower(),
    )