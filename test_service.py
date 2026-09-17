from datetime import datetime, timezone

from pdf_service import generate_pdf
from response_utils import response
from s3_service import (
    get_template,
    save_signed_pdf,
)


def consent_is_accepted(value):
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def handle_manual_test(data):
    full_name = str(
        data.get("full_name", "")
    ).strip()

    signature = str(
        data.get("signature", "")
    ).strip()

    order_number = str(
        data.get("order_number", "")
    ).strip()

    consent_accepted = data.get(
        "consent_accepted"
    )

    if not consent_is_accepted(
        consent_accepted
    ):
        return response(
            400,
            {"error": "Consent must be accepted."}
        )

    if (
        not full_name
        or not signature
        or not order_number
    ):
        return response(
            400,
            {"error": "Required test data is missing."}
        )

    signed_date = datetime.now(
        timezone.utc
    ).strftime("%m/%d/%Y")

    template = get_template()

    signed_pdf = generate_pdf(
        template_bytes=template,
        full_name=full_name,
        signature=signature,
        signed_date=signed_date,
        order_number=order_number,
    )

    agreement_key = save_signed_pdf(
        pdf_bytes=signed_pdf,
        order_number=order_number,
    )

    return response(
        200,
        {
            "success": True,
            "agreement_key": agreement_key,
        }
    )