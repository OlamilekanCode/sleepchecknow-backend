import json
from datetime import datetime, timezone

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


def lambda_handler(event, context):
    try:
        # API Gateway will normally send body as JSON string
        body = event.get("body", event)

        if isinstance(body, str):
            body = json.loads(body)

        full_name = str(body.get("full_name", "")).strip()
        signature = str(body.get("signature", "")).strip()
        order_number = str(body.get("order_number", "")).strip()
        consent_accepted = body.get("consent_accepted", False)

        if not consent_accepted:
            return response(400, {
                "error": "Consent must be accepted."
            })

        if not full_name or not signature or not order_number:
            return response(400, {
                "error": "full_name, signature and order_number are required."
            })

        # For now. Later we'll use the actual consent timestamp from Webflow.
        signed_date = datetime.now(timezone.utc).strftime("%m/%d/%Y")

        template = get_template()

        signed_pdf = generate_pdf(
            template_bytes=template,
            full_name=full_name,
            signature=signature,
            signed_date=signed_date,
            order_number=order_number,
        )

        s3_key = save_signed_pdf(
            pdf_bytes=signed_pdf,
            order_number=order_number,
        )

        return response(200, {
            "success": True,
            "agreement_key": s3_key
        })

    except Exception:
        # Important: don't expose PHI/internal AWS errors to the caller
        return response(500, {
            "error": "Agreement processing failed."
        })