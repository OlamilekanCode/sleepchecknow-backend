import json
import logging

from response_utils import response
from test_service import handle_manual_test
from webhook_security import verify_webflow_signature
from webflow_service import handle_webflow_order


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    request_id = getattr(
        context,
        "aws_request_id",
        "unknown",
    )

    try:
        # Requests coming through API Gateway
        is_http_request = bool(
            event.get("requestContext")
        )

        if is_http_request:
            if not verify_webflow_signature(event):
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

            body = event.get(
                "body",
                "{}",
            )

            if isinstance(body, str):
                body = json.loads(body)

            if not isinstance(body, dict):
                return response(
                    400,
                    {
                        "error":
                        "Invalid request body."
                    },
                )

            return handle_webflow_order(
                body
            )

        # Direct AWS Lambda console testing
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

    except Exception as error:
        # Log only safe technical information.
        # Never log the webhook body or patient data.
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
                "Agreement processing failed."
            },
        )