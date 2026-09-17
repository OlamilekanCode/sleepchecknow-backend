from datetime import datetime

from pdf_service import generate_pdf
from response_utils import response
from s3_service import (
    get_template,
    save_signed_pdf,
)


CONSENT_VERSION = "SCN-CONSENT-v1"


def parse_custom_data(custom_data):
    result = {}

    for item in custom_data or []:
        name = item.get("name")

        if not name:
            continue

        if "textInput" in item:
            value = item["textInput"]

        elif "textArea" in item:
            value = item["textArea"]

        elif "checkbox" in item:
            value = item["checkbox"]

        else:
            continue

        result[name] = value

    return result


def consent_is_accepted(value):
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def format_signed_date(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00"
            )
        )

        return parsed.strftime(
            "%m/%d/%Y"
        )

    except (ValueError, TypeError):
        return None


def handle_webflow_order(data):
    if data.get("triggerType") != "ecomm_new_order":
        return response(
            400,
            {"error": "Unsupported webhook event."}
        )

    order = data.get("payload") or {}

    order_number = str(
        order.get("orderId", "")
    ).strip()

    custom_data = parse_custom_data(
        order.get("customData", [])
    )

    signature = str(
        custom_data.get(
            "consent_signature",
            ""
        )
    ).strip()

    consent_accepted = custom_data.get(
        "consent_accepted"
    )

    consent_version = str(
        custom_data.get(
            "consent_version",
            ""
        )
    ).strip()

    signed_at = custom_data.get(
        "consent_signed_at"
    )

    # Fallback to Webflow's actual order timestamp
    if not signed_at:
        signed_at = order.get(
            "acceptedOn"
        )

    signed_date = format_signed_date(
        signed_at
    )

    if not order_number:
        return response(
            400,
            {"error": "Missing Webflow order ID."}
        )

    if not consent_is_accepted(
        consent_accepted
    ):
        return response(
            400,
            {"error": "Consent was not accepted."}
        )

    if not signature:
        return response(
            400,
            {"error": "Electronic signature is missing."}
        )

    if consent_version != CONSENT_VERSION:
        return response(
            400,
            {
                "error":
                "Unsupported consent agreement version."
            }
        )

    if not signed_date:
        return response(
            400,
            {
                "error":
                "Consent timestamp is missing or invalid."
            }
        )

    template = get_template()

    signed_pdf = generate_pdf(
        template_bytes=template,
        full_name=signature,
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
            "order_number": order_number,
            "agreement_key": agreement_key,
        }
    )