import json
import re
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


BUCKET = "sleepchecknow-signed-agreements"
ORDER_PREFIX = "verified-webflow-orders"

s3 = boto3.client("s3")


def get_verified_order_key(order_id):
    order_id = str(order_id or "").strip()

    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", order_id):
        raise ValueError("Invalid Webflow order ID.")

    return f"{ORDER_PREFIX}/{order_id}.json"


def save_verified_webflow_order(order):
    """
    Records an order received through the
    signature-verified Webflow webhook.

    This does NOT confirm successful payment.
    This does NOT link consent, generate a PDF,
    or send an email.
    """

    order_id = str(
        order.get("orderId") or ""
    ).strip()

    customer_info = order.get("customerInfo") or {}

    customer_email = str(
        customer_info.get("email") or ""
    ).strip().lower()

    if not customer_email:
        raise ValueError("Customer email is missing.")

    stripe_details = order.get("stripeDetails") or {}
    metadata = order.get("metadata") or {}

    record = {
        "order_id": order_id,
        "customer_email": customer_email,
        "webflow_status": order.get("status"),
        "accepted_on": order.get("acceptedOn"),
        "payment_processor": metadata.get(
            "paymentProcessor"
        ),
        "stripe_payment_intent_id": stripe_details.get(
            "paymentIntentId"
        ),
        "consent_status": "awaiting_link",
        "payment_verified": False,
        "recorded_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    key = get_verified_order_key(order_id)

    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(record).encode("utf-8"),
            ContentType="application/json",
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
            .get("ResponseMetadata", {})
            .get("HTTPStatusCode")
        )

        if (
            error_code in {
                "PreconditionFailed",
                "ConditionalRequestConflict",
            }
            or status_code in {409, 412}
        ):
            # The order has already been recorded.
            return False

        raise


def get_verified_webflow_order(order_id):
    key = get_verified_order_key(order_id)

    try:
        result = s3.get_object(
            Bucket=BUCKET,
            Key=key,
        )

        return json.loads(
            result["Body"].read()
        )

    except ClientError as error:
        error_code = (
            error.response
            .get("Error", {})
            .get("Code")
        )

        if error_code in {"NoSuchKey", "404"}:
            return None

        raise