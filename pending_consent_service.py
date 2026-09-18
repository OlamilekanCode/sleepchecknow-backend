import json
import secrets
from datetime import datetime, timedelta, timezone

import boto3


BUCKET = "sleepchecknow-signed-agreements"
PENDING_PREFIX = "pending-consents"

CONSENT_VERSION = "SCN-CONSENT-v1"

s3 = boto3.client("s3")


def consent_is_accepted(value):
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def create_pending_consent(data):
    """
    Stores a signed consent temporarily before
    a Web Payment order exists.

    Does NOT generate a PDF.
    Does NOT send email.
    """

    required_fields = {
        "full_name": data.get("full_name"),
        "email": data.get("email"),
        "cell_number": data.get("cell_number"),
        "date_of_birth": data.get("date_of_birth"),
        "gender": data.get("gender"),
        "height": data.get("height"),
        "weight": data.get("weight"),
        "consent_signature": data.get(
            "consent_signature"
        ),
        "consent_signed_at": data.get(
            "consent_signed_at"
        ),
    }

    missing_fields = [
        field
        for field, value in required_fields.items()
        if not str(value or "").strip()
    ]

    if missing_fields:
        raise ValueError(
            "Missing required consent information."
        )

    if not consent_is_accepted(
        data.get("consent_accepted")
    ):
        raise ValueError(
            "Consent was not accepted."
        )

    consent_version = str(
        data.get(
            "consent_version",
            "",
        )
    ).strip()

    if consent_version != CONSENT_VERSION:
        raise ValueError(
            "Unsupported consent agreement version."
        )

    token = secrets.token_urlsafe(32)

    now = datetime.now(timezone.utc)

    # Pending consent is valid for 2 hours.
    expires_at = now + timedelta(hours=2)

    record = {
        "consent_token": token,
        "status": "pending_payment",
        "payment_flow": "web_payment",

        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),

        "full_name": str(
            data["full_name"]
        ).strip(),

        "email": str(
            data["email"]
        ).strip(),

        "cell_number": str(
            data["cell_number"]
        ).strip(),

        "date_of_birth": str(
            data["date_of_birth"]
        ).strip(),

        "gender": str(
            data["gender"]
        ).strip(),

        "height": str(
            data["height"]
        ).strip(),

        "weight": str(
            data["weight"]
        ).strip(),

        "consent_signature": str(
            data["consent_signature"]
        ).strip(),

        "consent_accepted": True,

        "consent_version": consent_version,

        "consent_signed_at": str(
            data["consent_signed_at"]
        ).strip(),
    }

    key = (
        f"{PENDING_PREFIX}/{token}.json"
    )

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(record).encode("utf-8"),
        ContentType="application/json",
    )

    return {
        "consent_token": token,
        "expires_at": record["expires_at"],
    }