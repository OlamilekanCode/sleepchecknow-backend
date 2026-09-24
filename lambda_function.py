
import json
import logging

from pending_consent_service import (
    create_pending_consent,
    link_pending_consent,
)
from response_utils import response
from test_service import handle_manual_test
from webhook_security import verify_webflow_signature
from webflow_service import handle_webflow_order
from web_payment_agreement_service import (
    finalize_web_payment_agreement,
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_request_path(event):
    path = event.get("rawPath")

    if path:
        return path

    request_context = event.get(
        "requestContext",
        {},
    )

    http_context = request_context.get(
        "http",
        {},
    )

    return http_context.get(
        "path",
        "",
    )


def parse_request_body(event):
    body = event.get(
        "body",
        "{}",
    )

    if isinstance(body, str):
        return json.loads(body)

    if isinstance(body, dict):
        return body

    raise ValueError(
        "Invalid request body."
    )


def handle_pending_consent(event):
    try:
        body = parse_request_body(
            event
        )

        result = create_pending_consent(
            body
        )

        return response(
            201,
            {
                "success": True,
                "consent_token":
                    result["consent_token"],
                "expires_at":
                    result["expires_at"],
            },
        )

    except ValueError as error:
        return response(
            400,
            {
                "success": False,
                "error": str(error),
            },
        )


def handle_consent_link(event):
    try:
        body = parse_request_body(
            event
        )

        order_id = body.get(
            "order_id"
        )

        consent_token = body.get(
            "consent_token"
        )

        # Link the saved consent to a genuine
        # Webflow order received through the
        # signature-verified order webhook.

        link_result = link_pending_consent(
            order_id=order_id,
            consent_token=consent_token,
        )

        # The order and consent are now linked.
        #
        # Generate the signed PDF and send the
        # agreement to the business mailbox.
        #
        # The finalization service uses the
        # existing S3 processing marker to
        # prevent duplicate agreement emails.

        agreement_result = (
            finalize_web_payment_agreement(
                order_id=order_id,
                consent_token=consent_token,
            )
        )

        processing_status = (
            agreement_result.get(
                "processing_status",
                "unknown",
            )
        )

        # A previous invocation may already
        # be processing this order.
        #
        # Allow the confirmation page to retry
        # without starting another email send.

        if not agreement_result["success"]:
            if agreement_result.get(
                "manual_review"
            ):
                return response(
                    200,
                    {
                        "success": False,
                        "retry": False,
                        "order_id": order_id,
                        "linked": True,
                        "agreement_status":
                            processing_status,
                        "manual_review_required":
                            True,
                        "error":
                            "Agreement delivery "
                            "requires manual review.",
                    },
                )

            return response(
                409,
                {
                    "success": False,
                    "retry": True,
                    "order_id": order_id,
                    "linked": True,
                    "agreement_status":
                        processing_status,
                    "error":
                        "Agreement processing "
                        "is still underway.",
                },
            )

        return response(
            200,
            {
                "success": True,
                "order_id": order_id,
                "linked":
                    link_result["linked"],
                "already_linked":
                    link_result[
                        "already_linked"
                    ],
                "already_processed":
                    agreement_result.get(
                        "already_processed",
                        False,
                    ),
                "agreement_status":
                    "completed",
                "admin_email_sent": True,
                "customer_email_sent": False,
                "manual_review_required":
                    False,
            },
        )

    except ValueError as error:
        error_message = str(error)

        # Webflow's order webhook may arrive
        # after the customer reaches the
        # order-confirmation page.
        #
        # The existing confirmation-page
        # script can retry these responses.

        if error_message in {
            "Verified Webflow order is not available yet.",
            "Webflow order is not ready for consent linking.",
        }:
            return response(
                409,
                {
                    "success": False,
                    "retry": True,
                    "error":
                        "Order verification "
                        "is not ready yet.",
                },
            )

        return response(
            400,
            {
                "success": False,
                "retry": False,
                "error": error_message,
            },
        )


def lambda_handler(event, context):
    request_id = getattr(
        context,
        "aws_request_id",
        "unknown",
    )

    try:
        is_http_request = bool(
            event.get(
                "requestContext"
            )
        )

        if is_http_request:
            path = get_request_path(
                event
            )

            # ---------------------------------
            # Save pending Web Payment consent.
            # ---------------------------------

            if path == "/consent/pending":
                return handle_pending_consent(
                    event
                )

            # ---------------------------------
            # Link consent to the genuine
            # Webflow order and finalize the
            # signed agreement.
            # ---------------------------------

            if path == "/consent/link":
                return handle_consent_link(
                    event
                )

            # ---------------------------------
            # Genuine Webflow order webhook.
            # ---------------------------------

            if path == "/webflow/order":
                if not verify_webflow_signature(
                    event
                ):
                    logger.warning(
                        "Rejected invalid webhook signature. "
                        "request_id=%s",
                        request_id,
                    )

                    return response(
                        401,
                        {
                            "error":
                                "Invalid webhook signature."
                        },
                    )

                body = parse_request_body(
                    event
                )

                return handle_webflow_order(
                    body
                )

            return response(
                404,
                {
                    "error":
                        "Endpoint not found."
                },
            )

        # Direct AWS Lambda console testing.
        logger.info(
            "Manual Lambda test invoked. "
            "request_id=%s",
            request_id,
        )

        return handle_manual_test(
            event
        )

    except json.JSONDecodeError:
        logger.warning(
            "Invalid JSON request. "
            "request_id=%s",
            request_id,
        )

        return response(
            400,
            {
                "error":
                    "Invalid JSON request."
            },
        )

    except ValueError:
        return response(
            400,
            {
                "error":
                    "Invalid request body."
            },
        )

    except Exception as error:
        logger.error(
            "Unhandled Lambda error. "
            "request_id=%s error_type=%s",
            request_id,
            type(error).__name__,
        )

        return response(
            500,
            {
                "error":
                    "Request processing failed."
            },
        )