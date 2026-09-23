import json
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


BUCKET = "sleepchecknow-signed-agreements"
TEMPLATE_KEY = "templates/patient-consent-v1.pdf"
PROCESSED_PREFIX = "processed"

s3 = boto3.client("s3")


def get_template():
    response = s3.get_object(
        Bucket=BUCKET,
        Key=TEMPLATE_KEY,
    )

    return response["Body"].read()


def save_signed_pdf(pdf_bytes, order_number):
    key = f"signed/{order_number}-signed-agreement.pdf"

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    return key


def get_processing_key(order_number):
    return f"{PROCESSED_PREFIX}/{order_number}.json"


def _write_order_marker(
    order_number,
    status,
    agreement_key=None,
    email_message_id=None,
):
    key = get_processing_key(order_number)

    marker = {
        "order_id": order_number,
        "status": status,
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    if agreement_key:
        marker["agreement_key"] = agreement_key

    if email_message_id:
        marker["email_message_id"] = email_message_id

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(marker).encode("utf-8"),
        ContentType="application/json",
    )


def claim_order_processing(order_number):
    """
    Atomically claims an order.

    Returns:
        True  -> this invocation owns the order.
        False -> the order already has a marker.
    """

    key = get_processing_key(order_number)

    marker = {
        "order_id": order_number,
        "status": "processing",
        "updated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(marker).encode("utf-8"),
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
            error_code
            in {
                "PreconditionFailed",
                "ConditionalRequestConflict",
            }
            or status_code in {409, 412}
        ):
            return False

        raise


def get_order_status(order_number):
    """
    Returns the current processing status.

    Returns None if no marker exists.
    """

    key = get_processing_key(order_number)

    try:
        response = s3.get_object(
            Bucket=BUCKET,
            Key=key,
        )

        marker = json.loads(
            response["Body"].read()
        )

        return marker.get("status")

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


def mark_order_pdf_saved(
    order_number,
    agreement_key,
):
    _write_order_marker(
        order_number=order_number,
        status="pdf_saved",
        agreement_key=agreement_key,
    )


def mark_order_email_sending(
    order_number,
    agreement_key,
):
    _write_order_marker(
        order_number=order_number,
        status="email_sending",
        agreement_key=agreement_key,
    )


def mark_order_completed(
    order_number,
    agreement_key,
    email_message_id,
):
    _write_order_marker(
        order_number=order_number,
        status="completed",
        agreement_key=agreement_key,
        email_message_id=email_message_id,
    )


def release_order_claim(order_number):
    """
    Deletes a marker only when it is safe to retry.

    Do NOT call this after email sending has started.
    """

    key = get_processing_key(order_number)

    s3.delete_object(
        Bucket=BUCKET,
        Key=key,
    )

def mark_order_email_result(
    order_number,
    agreement_key,
    customer_sent,
    admin_sent,
    customer_message_id=None,
    admin_message_id=None,
    customer_error_type=None,
    admin_error_type=None,
):
    if customer_sent and admin_sent:
        status = "completed"

    elif customer_sent or admin_sent:
        status = "partial_email_delivery"

    else:
        status = "email_failed"

    key = get_processing_key(
        order_number
    )

    marker = {
        "order_id":
            order_number,
        "status":
            status,
        "updated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "agreement_key":
            agreement_key,
        "customer_email_sent":
            bool(customer_sent),
        "admin_email_sent":
            bool(admin_sent),
    }

    if customer_message_id:
        marker[
            "customer_email_message_id"
        ] = customer_message_id

    if admin_message_id:
        marker[
            "admin_email_message_id"
        ] = admin_message_id

    if customer_error_type:
        marker[
            "customer_email_error_type"
        ] = customer_error_type

    if admin_error_type:
        marker[
            "admin_email_error_type"
        ] = admin_error_type

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(
            marker
        ).encode("utf-8"),
        ContentType=
            "application/json",
    )

    return status