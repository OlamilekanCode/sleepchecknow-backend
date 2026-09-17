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


def claim_order_processing(order_number):
    """
    Atomically claims an order before processing it.

    Returns:
        True  -> this Lambda invocation can process the order.
        False -> another invocation already claimed/processed it.
    """

    key = get_processing_key(order_number)

    marker = {
        "order_id": order_number,
        "status": "processing",
        "claimed_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    try:
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=json.dumps(marker).encode("utf-8"),
            ContentType="application/json",

            # Only create the object if it does not already exist.
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


def mark_order_completed(
    order_number,
    agreement_key,
):
    """
    Changes the processing marker to completed
    after the order finishes successfully.
    """

    key = get_processing_key(order_number)

    marker = {
        "order_id": order_number,
        "status": "completed",
        "agreement_key": agreement_key,
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(marker).encode("utf-8"),
        ContentType="application/json",
    )


def release_order_claim(order_number):
    """
    Removes the processing marker when processing fails.

    This allows Webflow's next retry to try the order again.
    """

    key = get_processing_key(order_number)

    s3.delete_object(
        Bucket=BUCKET,
        Key=key,
    )