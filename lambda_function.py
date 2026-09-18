import json
import logging

from pending_consent_service import create_pending_consent
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
        {}
    )

    http_context = request_context.get(
        "http",
        {}
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
        body = parse_request_body(event)

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


def lambda_handler(event, context):
    request_id = getattr(
        context,
        "aws_request_id",
        "unknown",
    )

    try:
        is_http_request = bool(
            event.get("requestContext")
        )

        if is_http_request:
            path = get_request_path(
                event
            )

            # Web Payments pending consent endpoint.
            if path == "/consent/pending":
                return handle_pending_consent(
                    event
                )

            # Webflow order webhook.
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