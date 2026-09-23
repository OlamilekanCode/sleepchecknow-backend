import html
import os

import boto3
from email.message import EmailMessage
from botocore.exceptions import ClientError


LOGO_URL = (
    "https://cdn.prod.website-files.com/"
    "69e796510c62f93bdaa2b7f6/"
    "6a74b15d483f7344724e5636_Logo%20FINAL-p-1080.png"
)

SES_CONFIGURATION_SET = os.getenv(
    "SES_CONFIGURATION_SET",
    "SleepCheckNow-Transactional",
)

ADMIN_AGREEMENT_EMAIL = os.getenv(
    "ADMIN_AGREEMENT_EMAIL",
    "support@homesleephealth.com",
).strip()


ses = boto3.client(
    "ses",
    region_name=os.getenv(
        "AWS_REGION",
        "eu-north-1",
    ),
)


def send_agreement_email(
    recipient_email: str,
    pdf_bytes: bytes,
    order_number: str,
    customer_name: str | None = None,
):
    """
    Sends the signed consent agreement PDF to:
    - the customer
    - the SleepCheckNow business/admin email

    A single SES message is used so both recipients
    receive the exact same signed agreement.
    """

    sender_email = os.getenv(
        "SES_FROM_EMAIL"
    )

    if not sender_email:
        raise ValueError(
            "SES_FROM_EMAIL environment variable "
            "is not configured"
        )

    recipient_email = str(
        recipient_email or ""
    ).strip()

    if not recipient_email:
        raise ValueError(
            "Recipient email is required"
        )

    if not pdf_bytes:
        raise ValueError(
            "PDF content is required"
        )

    if not ADMIN_AGREEMENT_EMAIL:
        raise ValueError(
            "Admin agreement email is not configured"
        )

    display_name = (
        customer_name
        or "Customer"
    )

    safe_name = html.escape(
        display_name
    )

    safe_order_number = html.escape(
        order_number
    )

    message = EmailMessage()

    message["Subject"] = (
        "Your SleepCheckNow Signed Agreement "
        f"- {order_number}"
    )

    message["From"] = (
        f"SleepCheckNow <{sender_email}>"
    )

    # Only show the customer in the visible To header.
    #
    # The business copy is supplied separately to SES
    # through Destinations so it behaves like a BCC copy.
    message["To"] = recipient_email

    # Plain-text fallback
    message.set_content(
        f"Hello {display_name},\n\n"
        "Thank you for your order with SleepCheckNow.\n\n"
        "Your signed Patient Consent, Terms of Service & Release "
        "agreement is attached to this email for your records.\n\n"
        f"Order: {order_number}\n\n"
        "SleepCheckNow / Home Sleep Health\n\n"
        "This is an automated email. Please do not reply."
    )

    # HTML email
    message.add_alternative(
        f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
</head>

<body
    style="
        margin: 0;
        padding: 0;
        background-color: #f4f7fa;
        font-family: Arial, Helvetica, sans-serif;
        color: #1f2937;
    "
>
<table
    role="presentation"
    width="100%"
    cellspacing="0"
    cellpadding="0"
    border="0"
    style="background-color: #f4f7fa;"
>
    <tr>
        <td
            align="center"
            style="padding: 40px 16px;"
        >
            <table
                role="presentation"
                width="100%"
                cellspacing="0"
                cellpadding="0"
                border="0"
                style="
                    max-width: 600px;
                    background-color: #ffffff;
                    border-radius: 10px;
                    overflow: hidden;
                "
            >
                <tr>
                    <td
                        align="center"
                        style="
                            padding: 28px 32px 24px;
                            background-color: #ffffff;
                            border-bottom: 1px solid #e5e7eb;
                        "
                    >
                        <img
                            src="{LOGO_URL}"
                            alt="SleepCheckNow"
                            width="210"
                            style="
                                display: block;
                                width: 210px;
                                max-width: 100%;
                                height: auto;
                                border: 0;
                            "
                        >
                    </td>
                </tr>

                <tr>
                    <td
                        style="
                            padding: 36px 32px;
                        "
                    >
                        <h1
                            style="
                                margin: 0 0 20px;
                                font-size: 22px;
                                line-height: 1.35;
                                color: #111827;
                            "
                        >
                            Your signed agreement is ready
                        </h1>

                        <p
                            style="
                                margin: 0 0 18px;
                                font-size: 16px;
                                line-height: 1.6;
                            "
                        >
                            Hello {safe_name},
                        </p>

                        <p
                            style="
                                margin: 0 0 18px;
                                font-size: 16px;
                                line-height: 1.6;
                            "
                        >
                            Thank you for your order with
                            SleepCheckNow.
                        </p>

                        <p
                            style="
                                margin: 0 0 24px;
                                font-size: 16px;
                                line-height: 1.6;
                            "
                        >
                            Attached is a copy of your signed
                            Patient Consent, Terms of Service
                            &amp; Release agreement for your records.
                        </p>

                        <table
                            role="presentation"
                            width="100%"
                            cellspacing="0"
                            cellpadding="0"
                            border="0"
                            style="
                                background-color: #f7fafc;
                                border-radius: 8px;
                                margin-bottom: 26px;
                            "
                        >
                            <tr>
                                <td
                                    style="
                                        padding: 18px;
                                        font-size: 14px;
                                        color: #6b7280;
                                    "
                                >
                                    Order reference
                                    <br>

                                    <strong
                                        style="
                                            display: inline-block;
                                            margin-top: 6px;
                                            color: #111827;
                                            font-size: 16px;
                                        "
                                    >
                                        {safe_order_number}
                                    </strong>
                                </td>
                            </tr>
                        </table>

                        <p
                            style="
                                margin: 0;
                                font-size: 14px;
                                line-height: 1.6;
                                color: #6b7280;
                            "
                        >
                            Your signed agreement is included
                            as a PDF attachment to this email.
                        </p>
                    </td>
                </tr>

                <tr>
                    <td
                        style="
                            padding: 22px 32px;
                            border-top: 1px solid #e5e7eb;
                            text-align: center;
                            color: #6b7280;
                            font-size: 12px;
                            line-height: 1.6;
                        "
                    >
                        SleepCheckNow / Home Sleep Health
                        <br>
                        This is an automated transactional email.
                        Please do not reply.
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>
</body>
</html>
""",
        subtype="html",
    )

    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=(
            f"{order_number}"
            "-signed-agreement.pdf"
        ),
    )
    
    raw_message = {
        "Data": message.as_bytes()
    }

    def send_one(destination):
        try:
            result = ses.send_raw_email(
                Source=sender_email,
                Destinations=[
                    destination
                ],
                RawMessage=raw_message,
                ConfigurationSetName=
                    SES_CONFIGURATION_SET,
            )

            return {
                "sent": True,
                "message_id":
                    result["MessageId"],
                "error_type": None,
            }

        except ClientError as error:
            return {
                "sent": False,
                "message_id": None,
                "error_type": (
                    error.response
                    .get("Error", {})
                    .get("Code")
                    or type(error).__name__
                ),
            }

    # Customer and business are now completely
    # independent SES deliveries.
    customer_delivery = send_one(
        recipient_email
    )

    if (
        recipient_email.lower()
        == ADMIN_AGREEMENT_EMAIL.lower()
    ):
        # Avoid sending the same email twice.
        admin_delivery = {
            **customer_delivery,
            "same_as_customer": True,
        }

    else:
        admin_delivery = send_one(
            ADMIN_AGREEMENT_EMAIL
        )

    return {
        # Keep these for backwards compatibility.
        "message_id": (
            customer_delivery["message_id"]
            or admin_delivery["message_id"]
        ),
        "recipient":
            recipient_email,
        "admin_recipient":
            ADMIN_AGREEMENT_EMAIL,

        # New independent delivery results.
        "customer":
            customer_delivery,
        "admin":
            admin_delivery,

        "customer_sent":
            customer_delivery["sent"],
        "admin_sent":
            admin_delivery["sent"],

        "any_sent": (
            customer_delivery["sent"]
            or admin_delivery["sent"]
        ),

        "all_sent": (
            customer_delivery["sent"]
            and admin_delivery["sent"]
        ),
    }