from datetime import datetime
import logging

from email_service import send_agreement_email
from pdf_service import generate_pdf
from response_utils import response
from s3_service import (
    claim_order_processing,
    get_order_status,
    get_template,
    mark_order_completed,
    mark_order_email_sending,
    mark_order_pdf_saved,
    release_order_claim,
    save_signed_pdf,
)
from verified_order_service import (
    save_verified_webflow_order,
)


CONSENT_VERSION = "SCN-CONSENT-v1"

CONSENT_FIELDS = {
    "consent_signature",
    "consent_accepted",
    "consent_version",
    "consent_signed_at",
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
                "+00:00",
            )
        )

        return parsed.strftime(
            "%m/%d/%Y"
        )

    except (ValueError, TypeError):
        return None


def handle_webflow_order(data):
    if (
        data.get("triggerType")
        != "ecomm_new_order"
    ):
        return response(
            400,
            {
                "error":
                    "Unsupported webhook event."
            },
        )

    order = (
        data.get("payload")
        or {}
    )

    order_number = str(
        order.get(
            "orderId",
            "",
        )
    ).strip()

    customer_info = (
        order.get("customerInfo")
        or {}
    )

    customer_name = str(
        customer_info.get(
            "fullName",
            "",
        )
    ).strip()

    customer_email = str(
        customer_info.get(
            "email",
            "",
        )
    ).strip()

    custom_data = parse_custom_data(
        order.get(
            "customData",
            [],
        )
    )

    if not order_number:
        return response(
            400,
            {
                "error":
                    "Missing Webflow order ID."
            },
        )

    if not customer_email:
        return response(
            400,
            {
                "error":
                    "Customer email is missing."
            },
        )

    present_consent_fields = (
        CONSENT_FIELDS.intersection(
            custom_data.keys()
        )
    )

    # --------------------------------------------------
    # WEB PAYMENT ORDER
    #
    # Apple Pay / Google Pay / browser payments do not
    # carry our Checkout consent fields.
    #
    # The webhook itself is already signature verified
    # before reaching this function.
    #
    # Store the genuine Webflow order for later linking.
    #
    # NO PDF.
    # NO EMAIL.
    # --------------------------------------------------

    if not present_consent_fields:
        newly_recorded = (
            save_verified_webflow_order(
                order
            )
        )

        return response(
            200,
            {
                "success": True,
                "order_number":
                    order_number,
                "agreement_status":
                    "awaiting_consent_link",
                "newly_recorded":
                    newly_recorded,
                "email_sent": False,
            },
        )

    # --------------------------------------------------
    # CARD / PAYPAL ORDER
    #
    # If consent fields exist, ALL four must exist.
    # --------------------------------------------------

    if (
        present_consent_fields
        != CONSENT_FIELDS
    ):
        return response(
            400,
            {
                "error":
                    "Incomplete consent information."
            },
        )

    signature = str(
        custom_data.get(
            "consent_signature",
            "",
        )
    ).strip()

    consent_accepted = (
        custom_data.get(
            "consent_accepted"
        )
    )

    consent_version = str(
        custom_data.get(
            "consent_version",
            "",
        )
    ).strip()

    signed_at = (
        custom_data.get(
            "consent_signed_at"
        )
    )

    if not signed_at:
        signed_at = order.get(
            "acceptedOn"
        )

    signed_date = (
        format_signed_date(
            signed_at
        )
    )

    if not consent_is_accepted(
        consent_accepted
    ):
        return response(
            400,
            {
                "error":
                    "Consent was not accepted."
            },
        )

    if not signature:
        return response(
            400,
            {
                "error":
                    "Electronic signature is missing."
            },
        )

    if (
        consent_version
        != CONSENT_VERSION
    ):
        return response(
            400,
            {
                "error":
                    "Unsupported consent agreement version."
            },
        )

    if not signed_date:
        return response(
            400,
            {
                "error":
                    "Consent timestamp is missing or invalid."
            },
        )

    # --------------------------------------------------
    # EXISTING CARD / PAYPAL PROCESSING
    # --------------------------------------------------

    claimed = (
        claim_order_processing(
            order_number
        )
    )

    if not claimed:
        existing_status = (
            get_order_status(
                order_number
            )
        )

        return response(
            200,
            {
                "success": True,
                "duplicate": True,
                "order_number":
                    order_number,
                "processing_status":
                    existing_status
                    or "unknown",
                "message":
                    "Order already has a processing record.",
            },
        )

    processing_status = (
        "processing"
    )

    try:
        template = get_template()

        signed_pdf = generate_pdf(
            template_bytes=template,
            full_name=signature,
            signature=signature,
            signed_date=signed_date,
            order_number=order_number,
        )

        agreement_key = (
            save_signed_pdf(
                pdf_bytes=signed_pdf,
                order_number=
                    order_number,
            )
        )

        mark_order_pdf_saved(
            order_number=
                order_number,
            agreement_key=
                agreement_key,
        )

        processing_status = (
            "pdf_saved"
        )

        mark_order_email_sending(
            order_number=
                order_number,
            agreement_key=
                agreement_key,
        )

        processing_status = (
            "email_sending"
        )

        email_result = (
            send_agreement_email(
                recipient_email=
                    customer_email,
                pdf_bytes=
                    signed_pdf,
                order_number=
                    order_number,
                customer_name=(
                    customer_name
                    or signature
                ),
            )
        )

        mark_order_completed(
            order_number=
                order_number,
            agreement_key=
                agreement_key,
            email_message_id=(
                email_result[
                    "message_id"
                ]
            ),
        )

        processing_status = (
            "completed"
        )

        return response(
            200,
            {
                "success": True,
                "duplicate": False,
                "order_number":
                    order_number,
                "agreement_key":
                    agreement_key,
                "email_sent": True,
                "email_message_id":
                    email_result[
                        "message_id"
                    ],
            },
        )

    except Exception as error:
        if processing_status in {
            "processing",
            "pdf_saved",
        }:
            try:
                release_order_claim(
                    order_number
                )

            except Exception as release_error:
                logger.error(
                    "Failed to release order claim. "
                    "error_type=%s",
                    type(
                        release_error
                    ).__name__,
                )

        else:
            logger.warning(
                "Order marker preserved after email "
                "sending began. status=%s",
                processing_status,
            )

        logger.error(
            "Order processing failed. "
            "error_type=%s",
            type(error).__name__,
        )

        return response(
            500,
            {
                "success": False,
                "error":
                    "Order processing failed. "
                    "Manual review may be required "
                    "before retrying.",
            },
        )