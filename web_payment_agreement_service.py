from datetime import datetime
import logging

from email_service import send_agreement_email
from pdf_service import generate_pdf
from pending_consent_service import (
    load_pending_consent,
)
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
    get_verified_webflow_order,
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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


def finalize_web_payment_agreement(
    order_id,
    consent_token,
):
    """
    Finalizes a Web Payment agreement only
    after the pending consent has already been
    securely linked to the verified Webflow order.
    """

    consent = load_pending_consent(
        consent_token
    )

    if not consent:
        raise ValueError(
            "Linked consent was not found."
        )

    if (
        consent.get("status")
        != "linked"
    ):
        raise ValueError(
            "Consent is not linked."
        )

    if (
        consent.get("order_id")
        != order_id
    ):
        raise ValueError(
            "Consent does not match this order."
        )

    verified_order = (
        get_verified_webflow_order(
            order_id
        )
    )

    if not verified_order:
        raise ValueError(
            "Verified Webflow order was not found."
        )

    signature = str(
        consent.get(
            "consent_signature",
            "",
        )
    ).strip()

    full_name = str(
        consent.get(
            "full_name",
            "",
        )
    ).strip()

    customer_email = str(
        verified_order.get(
            "customer_email",
            "",
        )
    ).strip()

    customer_name = str(
        verified_order.get(
            "customer_name",
            "",
        )
    ).strip()

    signed_date = format_signed_date(
        consent.get(
            "consent_signed_at"
        )
    )

    if not signature:
        raise ValueError(
            "Electronic signature is missing."
        )

    if not customer_email:
        raise ValueError(
            "Customer email is missing."
        )

    if not signed_date:
        raise ValueError(
            "Consent timestamp is invalid."
        )

    claimed = claim_order_processing(
        order_id
    )

    if not claimed:
        existing_status = (
            get_order_status(
                order_id
            )
        )

        if existing_status == "completed":
            return {
                "success": True,
                "already_processed": True,
                "order_id": order_id,
                "processing_status":
                    "completed",
            }

        if existing_status == "email_sending":
            return {
                "success": False,
                "already_processed": False,
                "manual_review": True,
                "order_id": order_id,
                "processing_status":
                    "email_sending",
            }

        return {
            "success": False,
            "already_processed": False,
            "manual_review": False,
            "order_id": order_id,
            "processing_status":
                existing_status
                or "processing",
        }

    processing_status = "processing"

    try:
        template = get_template()

        signed_pdf = generate_pdf(
            template_bytes=template,
            full_name=(
                full_name
                or signature
            ),
            signature=signature,
            signed_date=signed_date,
            order_number=order_id,
        )

        agreement_key = (
            save_signed_pdf(
                pdf_bytes=signed_pdf,
                order_number=order_id,
            )
        )

        mark_order_pdf_saved(
            order_number=order_id,
            agreement_key=agreement_key,
        )

        processing_status = (
            "pdf_saved"
        )

        # IMPORTANT:

        # We record email_sending before
        # contacting SES.

        # If SES accepts the email and Lambda
        # fails immediately afterward, we do not
        # automatically send another copy.

        mark_order_email_sending(
            order_number=order_id,
            agreement_key=agreement_key,
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
                    order_id,

                customer_name=(
                    customer_name
                    or full_name
                    or signature
                ),
            )
        )

        mark_order_completed(
            order_number=order_id,
            agreement_key=agreement_key,
            email_message_id=(
                email_result[
                    "message_id"
                ]
            ),
        )

        processing_status = (
            "completed"
        )

        return {
            "success": True,
            "already_processed": False,
            "order_id": order_id,
            "processing_status":
                "completed",
            "agreement_key":
                agreement_key,
            "email_sent": True,
            "email_message_id":
                email_result[
                    "message_id"
                ],
        }

    except Exception as error:
        if processing_status in {
            "processing",
            "pdf_saved",
        }:
            try:
                release_order_claim(
                    order_id
                )

            except Exception as release_error:
                logger.error(
                    "Failed to release Web Payment "
                    "order claim. error_type=%s",
                    type(
                        release_error
                    ).__name__,
                )

        else:
            logger.warning(
                "Web Payment order marker preserved "
                "after email sending began. status=%s",
                processing_status,
            )

        logger.error(
            "Web Payment agreement processing failed. "
            "error_type=%s",
            type(error).__name__,
        )

        raise