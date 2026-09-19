import json
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


BUCKET = "sleepchecknow-signed-agreements"
ORDER_PREFIX = "verified-webflow-orders"

s3 = boto3.client("s3")


def get_verified_order_key(order_id):
    order_id = str(
        order_id or ""
    ).strip()

    if not re.fullmatch(
        r"[A-Za-z0-9-]{1,64}",
        order_id,
    ):
        raise ValueError(
            "Invalid Webflow order ID."
        )

    return (
        f"{ORDER_PREFIX}/"
        f"{order_id}.json"
    )


def save_verified_webflow_order(order):
    """
    Stores a minimal record of an order received
    through the signature-verified Webflow webhook.

    Does NOT generate an agreement.
    Does NOT send an email.
    """

    order_id = str(
        order.get("orderId") or ""
    ).strip()

    if not order_id:
        raise ValueError(
            "Webflow order ID is missing."
        )

    customer_info = (
        order.get("customerInfo")
        or {}
    )

    customer_name = str(
        customer_info.get(
            "fullName"
        )
        or ""
    ).strip()

    customer_email = str(
        customer_info.get(
            "email"
        )
        or ""
    ).strip().lower()

    if not customer_email:
        raise ValueError(
            "Customer email is missing."
        )

    stripe_details = (
        order.get("stripeDetails")
        or {}
    )

    metadata = (
        order.get("metadata")
        or {}
    )

    customer_paid = (
        order.get("customerPaid")
        or {}
    )

    record = {
        "order_id":
            order_id,

        "customer_name":
            customer_name,

        "customer_email":
            customer_email,

        "webflow_status":
            order.get("status"),

        "accepted_on":
            order.get("acceptedOn"),

        "payment_processor":
            metadata.get(
                "paymentProcessor"
            ),

        "stripe_payment_intent_id":
            stripe_details.get(
                "paymentIntentId"
            ),

        "stripe_charge_id":
            stripe_details.get(
                "chargeId"
            ),

        "customer_paid_value":
            customer_paid.get(
                "value"
            ),

        "customer_paid_currency":
            customer_paid.get(
                "unit"
            ),

        "consent_status":
            "awaiting_link",

        "recorded_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    key = get_verified_order_key(
        order_id
    )

    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(
                record
            ).encode("utf-8"),
            ContentType=
                "application/json",
            IfNoneMatch="*",
        )

        return True

    except ClientError as error:
        error_code = (
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
            error_code
            in {
                "PreconditionFailed",
                "ConditionalRequestConflict",
            }
            or status_code
            in {
                409,
                412,
            }
        ):
            return False

        raise


def get_verified_webflow_order(
    order_id,
):
    key = get_verified_order_key(
        order_id
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
        error_code = (
            error.response
            .get("Error", {})
            .get("Code")
        )

        if error_code in {
            "NoSuchKey",
            "404",
        }:
            return None

        raise


def is_verified_web_payment_order(
    record,
):
    """
    Checks whether the Webflow webhook record
    looks like a completed Stripe-backed order.

    This is used only after the record came from
    our signature-verified Webflow webhook.
    """

    if not record:
        return False

    status = str(
        record.get(
            "webflow_status"
        )
        or ""
    ).lower()

    payment_processor = str(
        record.get(
            "payment_processor"
        )
        or ""
    ).lower()

    payment_intent_id = (
        record.get(
            "stripe_payment_intent_id"
        )
    )

    accepted_on = (
        record.get(
            "accepted_on"
        )
    )

    return (
        status in {
            "unfulfilled",
            "fulfilled",
        }
        and payment_processor
        == "stripe"
        and bool(
            payment_intent_id
        )
        and bool(
            accepted_on
        )
    )