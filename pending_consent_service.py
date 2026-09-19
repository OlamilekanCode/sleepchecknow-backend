import json
import secrets
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

from verified_order_service import (
    get_verified_webflow_order,
    is_verified_web_payment_order,
)


BUCKET = "sleepchecknow-signed-agreements"

PENDING_PREFIX = "pending-consents"
LINK_PREFIX = "web-payment-links"

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


def normalize_email(value):
    return str(
        value or ""
    ).strip().lower()


def parse_datetime(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )

    except (ValueError, TypeError):
        return None


def get_pending_key(consent_token):
    return (
        f"{PENDING_PREFIX}/"
        f"{consent_token}.json"
    )


def get_link_key(order_id):
    return (
        f"{LINK_PREFIX}/"
        f"{order_id}.json"
    )


def load_pending_consent(consent_token):
    key = get_pending_key(
        consent_token
    )

    try:
        response = s3.get_object(
            Bucket=BUCKET,
            Key=key,
        )

        return json.loads(
            response["Body"].read()
        )

    except ClientError as error:
        code = (
            error.response
            .get("Error", {})
            .get("Code")
        )

        if code in {
            "NoSuchKey",
            "404",
        }:
            return None

        raise


def pending_consent_is_expired(record):
    expires_at = parse_datetime(
        record.get("expires_at")
    )

    if not expires_at:
        return True

    return (
        datetime.now(timezone.utc)
        >= expires_at
    )


def create_pending_consent(data):
    """
    Stores consent before a Web Payment
    order exists.

    No PDF is generated.
    No email is sent.
    """

    required_fields = {
        "full_name":
            data.get("full_name"),

        "email":
            data.get("email"),

        "cell_number":
            data.get("cell_number"),

        "date_of_birth":
            data.get("date_of_birth"),

        "gender":
            data.get("gender"),

        "height":
            data.get("height"),

        "weight":
            data.get("weight"),

        "consent_signature":
            data.get(
                "consent_signature"
            ),

        "consent_signed_at":
            data.get(
                "consent_signed_at"
            ),
    }

    missing_fields = [
        field
        for field, value
        in required_fields.items()
        if not str(
            value or ""
        ).strip()
    ]

    if missing_fields:
        raise ValueError(
            "Missing required consent information."
        )

    if not consent_is_accepted(
        data.get(
            "consent_accepted"
        )
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

    if (
        consent_version
        != CONSENT_VERSION
    ):
        raise ValueError(
            "Unsupported consent agreement version."
        )

    token = secrets.token_urlsafe(
        32
    )

    now = datetime.now(
        timezone.utc
    )

    expires_at = (
        now
        + timedelta(hours=2)
    )

    record = {
        "consent_token":
            token,

        "status":
            "pending_payment",

        "payment_flow":
            "web_payment",

        "created_at":
            now.isoformat(),

        "expires_at":
            expires_at.isoformat(),

        "full_name":
            str(
                data["full_name"]
            ).strip(),

        "email":
            normalize_email(
                data["email"]
            ),

        "cell_number":
            str(
                data["cell_number"]
            ).strip(),

        "date_of_birth":
            str(
                data["date_of_birth"]
            ).strip(),

        "gender":
            str(
                data["gender"]
            ).strip(),

        "height":
            str(
                data["height"]
            ).strip(),

        "weight":
            str(
                data["weight"]
            ).strip(),

        "consent_signature":
            str(
                data[
                    "consent_signature"
                ]
            ).strip(),

        "consent_accepted":
            True,

        "consent_version":
            consent_version,

        "consent_signed_at":
            str(
                data[
                    "consent_signed_at"
                ]
            ).strip(),
    }

    s3.put_object(
        Bucket=BUCKET,
        Key=get_pending_key(
            token
        ),
        Body=json.dumps(
            record
        ).encode("utf-8"),
        ContentType="application/json",
    )

    return {
        "consent_token":
            token,

        "expires_at":
            record["expires_at"],
    }


def link_pending_consent(
    order_id,
    consent_token,
):
    """
    Links a pending consent to a genuine
    Webflow Web Payment order.

    Safe to retry if a previous request
    partially completed.
    """

    order_id = str(
        order_id or ""
    ).strip()

    consent_token = str(
        consent_token or ""
    ).strip()

    if not order_id:
        raise ValueError(
            "Order ID is required."
        )

    if not consent_token:
        raise ValueError(
            "Consent token is required."
        )

    # ---------------------------------------
    # Load pending consent.
    # ---------------------------------------

    consent = load_pending_consent(
        consent_token
    )

    if not consent:
        raise ValueError(
            "Pending consent was not found."
        )

    existing_order_id = (
        consent.get("order_id")
    )

    consent_already_linked = (
        consent.get("status") == "linked"
        and existing_order_id == order_id
    )

    if (
        existing_order_id
        and existing_order_id != order_id
    ):
        raise ValueError(
            "Consent is already linked "
            "to another order."
        )

    # Only reject expiration if this consent
    # has not already been successfully linked.
    if (
        not consent_already_linked
        and pending_consent_is_expired(
            consent
        )
    ):
        raise ValueError(
            "Pending consent has expired."
        )

    # ---------------------------------------
    # Load genuine signed-webhook order.
    # ---------------------------------------

    verified_order = (
        get_verified_webflow_order(
            order_id
        )
    )

    if not verified_order:
        raise ValueError(
            "Verified Webflow order is not available yet."
        )

    if not is_verified_web_payment_order(
        verified_order
    ):
        raise ValueError(
            "Webflow order is not ready "
            "for consent linking."
        )

    # ---------------------------------------
    # Customer email must match.
    # ---------------------------------------

    consent_email = normalize_email(
        consent.get("email")
    )

    order_email = normalize_email(
        verified_order.get(
            "customer_email"
        )
    )

    if (
        not consent_email
        or not order_email
        or consent_email != order_email
    ):
        raise ValueError(
            "Order customer does not match "
            "the pending consent."
        )

    # ---------------------------------------
    # Verify timing.
    # ---------------------------------------

    consent_created_at = parse_datetime(
        consent.get(
            "created_at"
        )
    )

    consent_expires_at = parse_datetime(
        consent.get(
            "expires_at"
        )
    )

    order_accepted_at = parse_datetime(
        verified_order.get(
            "accepted_on"
        )
    )

    if (
        not consent_created_at
        or not consent_expires_at
        or not order_accepted_at
    ):
        raise ValueError(
            "Unable to verify order timing."
        )

    if (
        order_accepted_at
        < consent_created_at
    ):
        raise ValueError(
            "Order was created before "
            "the pending consent."
        )

    if (
        order_accepted_at
        > consent_expires_at
    ):
        raise ValueError(
            "Order was created after "
            "the pending consent expired."
        )

    # ---------------------------------------
    # Create order ↔ consent link.
    # ---------------------------------------

    now = datetime.now(
        timezone.utc
    )

    linked_at = now.isoformat()

    link_record = {
        "order_id":
            order_id,

        "consent_token":
            consent_token,

        "status":
            "verified",

        "verified_webflow_order":
            True,

        "payment_processor":
            verified_order.get(
                "payment_processor"
            ),

        "stripe_payment_intent_id":
            verified_order.get(
                "stripe_payment_intent_id"
            ),

        "linked_at":
            linked_at,
    }

    link_key = get_link_key(
        order_id
    )

    already_linked = False

    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=link_key,
            Body=json.dumps(
                link_record
            ).encode("utf-8"),
            ContentType="application/json",
            IfNoneMatch="*",
        )

    except ClientError as error:
        code = (
            error.response
            .get("Error", {})
            .get("Code")
        )

        status_code = (
            error.response
            .get(
                "ResponseMetadata",
                {},
            )
            .get(
                "HTTPStatusCode"
            )
        )

        if (
            code in {
                "PreconditionFailed",
                "ConditionalRequestConflict",
            }
            or status_code in {
                409,
                412,
            }
        ):
            existing_response = (
                s3.get_object(
                    Bucket=BUCKET,
                    Key=link_key,
                )
            )

            existing_link = json.loads(
                existing_response[
                    "Body"
                ].read()
            )

            if (
                existing_link.get(
                    "consent_token"
                )
                != consent_token
            ):
                raise ValueError(
                    "Order is already linked "
                    "to another consent."
                )

            already_linked = True

            linked_at = (
                existing_link.get(
                    "linked_at"
                )
                or linked_at
            )

        else:
            raise

    # ---------------------------------------
    # IMPORTANT:
    #
    # Always repair/update the pending consent,
    # even when the link object already existed.
    #
    # This fixes partial Lambda failures.
    # ---------------------------------------

    if (
        consent.get("status") != "linked"
        or consent.get("order_id") != order_id
    ):
        consent["status"] = "linked"
        consent["order_id"] = order_id
        consent["linked_at"] = linked_at

        s3.put_object(
            Bucket=BUCKET,
            Key=get_pending_key(
                consent_token
            ),
            Body=json.dumps(
                consent
            ).encode("utf-8"),
            ContentType="application/json",
        )

    return {
        "order_id":
            order_id,

        "linked":
            True,

        "already_linked":
            already_linked,
    }