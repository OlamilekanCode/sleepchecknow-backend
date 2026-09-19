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

        result = link_pending_consent(
            order_id=order_id,
            consent_token=consent_token,
        )

        return response(
            200,
            {
                "success": True,
                "order_id":
                    result["order_id"],
                "linked":
                    result["linked"],
                "already_linked":
                    result[
                        "already_linked"
                    ],
            },
        )

    except ValueError as error:
        error_message = str(error)

        # The confirmation page may arrive
        # before the Webflow webhook has been
        # processed by Lambda.
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
                        "Order verification is not ready yet.",
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
            # Link pending consent to the
            # genuine Webflow order.
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