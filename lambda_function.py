import json
from datetime import datetime

from pdf_service import generate_pdf
from s3_service import get_template, save_signed_pdf


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body)
    }


def parse_body(event):
    """
    API Gateway sends the HTTP request body as a JSON string.
    Lambda console tests may send the object directly.
    """

    body = event.get("body", event)

    if isinstance(body, str):
        return json.loads(body)

    return body


def parse_custom_data(custom_data):
    """
    Convert Webflow customData:

    [
        {
            "name": "consent_signature",
            "textInput": "Dev Test"
        }
    ]

    into:

    {
        "consent_signature": "Dev Test"
    }
    """

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
        "on"
    }


def format_signed_date(value):
    """
    Converts:
    2026-09-17T15:17:12.840Z

    into:
    09/17/2026
    """

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        return parsed.strftime("%m/%d/%Y")

    except (ValueError, TypeError):
        return None


def handle_webflow_order(data):
    # New Webflow webhook format:
    #
    # {
    #   "triggerType": "ecomm_new_order",
    #   "payload": {...}
    # }

    trigger_type = data.get("triggerType")

    if trigger_type and trigger_type != "ecomm_new_order":
        return response(
            400,
            {"error": "Unsupported webhook event."}
        )

    order = data.get("payload", data)

    order_number = str(
        order.get("orderId", "")
    ).strip()

    custom_data = parse_custom_data(
        order.get("customData", [])
    )

    signature = str(
        custom_data.get("consent_signature", "")
    ).strip()

    consent_accepted = custom_data.get(
        "consent_accepted"
    )

    consent_version = str(
        custom_data.get("consent_version", "")
    ).strip()

    signed_at = custom_data.get(
        "consent_signed_at"
    )

    # Fallback to Webflow's order timestamp
    if not signed_at:
        signed_at = order.get("acceptedOn")

    signed_date = format_signed_date(signed_at)

    if not order_number:
        return response(
            400,
            {"error": "Missing Webflow order ID."}
        )

    if not consent_is_accepted(consent_accepted):
        return response(
            400,
            {"error": "Consent was not accepted."}
        )

    if not signature:
        return response(
            400,
            {"error": "Electronic signature is missing."}
        )

    if not signed_date:
        return response(
            400,
            {"error": "Consent timestamp is missing or invalid."}
        )

    if consent_version != "SCN-CONSENT-v1":
        return response(
            400,
            {"error": "Unsupported consent agreement version."}
        )

    template = get_template()

    signed_pdf = generate_pdf(
        template_bytes=template,

        # Consent name is the legal name the user
        # intentionally typed when signing.
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
            "agreement_key": agreement_key
        }
    )


def handle_manual_test(data):
    """
    Keeps our original test format working.
    """

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

    if not consent_is_accepted(consent_accepted):
        return response(
            400,
            {"error": "Consent must be accepted."}
        )

    if not full_name or not signature or not order_number:
        return response(
            400,
            {
                "error":
                "full_name, signature and order_number are required."
            }
        )

    signed_date = datetime.utcnow().strftime(
        "%m/%d/%Y"
    )

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
            "agreement_key": agreement_key
        }
    )


def lambda_handler(event, context):
    try:
        data = parse_body(event)

        # Our original development payload
        if "full_name" in data:
            return handle_manual_test(data)

        # Real Webflow webhook
        return handle_webflow_order(data)

    except (json.JSONDecodeError, TypeError, ValueError):
        return response(
            400,
            {"error": "Invalid request."}
        )

    except Exception:
        # Never expose AWS/internal/PHI details
        return response(
            500,
            {"error": "Agreement processing failed."}
        )