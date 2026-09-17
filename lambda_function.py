import json

from response_utils import response
from test_service import handle_manual_test
from webhook_security import verify_webflow_signature
from webflow_service import handle_webflow_order


def lambda_handler(event, context):
    try:
        # Requests coming through API Gateway
        is_http_request = bool(event.get("requestContext"))

        if is_http_request:
            if not verify_webflow_signature(event):
                return response(
                    401,
                    {"error": "Invalid webhook signature."}
                )

            body = event.get("body", "{}")

            if isinstance(body, str):
                body = json.loads(body)

            return handle_webflow_order(body)

        # Direct AWS Lambda console testing
        return handle_manual_test(event)

    except json.JSONDecodeError:
        return response(
            400,
            {"error": "Invalid JSON request."}
        )

    except Exception:
        # Do not expose internal AWS errors or patient data
        return response(
            500,
            {"error": "Agreement processing failed."}
        )