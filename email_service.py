
import os
from email.message import EmailMessage

import boto3


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
    Send one signed-agreement email directly to
    the Home Sleep Health support mailbox.

    recipient_email is retained for compatibility
    with existing callers. It is NOT used as an
    email destination.
    """

    sender_email = os.getenv(
        "SES_FROM_EMAIL",
        "",
    ).strip()

    if not sender_email:
        raise ValueError(
            "SES_FROM_EMAIL is not configured."
        )

    if not ADMIN_AGREEMENT_EMAIL:
        raise ValueError(
            "Admin agreement email is not configured."
        )

    if not pdf_bytes:
        raise ValueError(
            "PDF content is required."
        )

    if not order_number:
        raise ValueError(
            "Order number is required."
        )

    patient_name = (
        str(customer_name or "").strip()
        or "Not provided"
    )

    message = EmailMessage()

    message["From"] = (
        f"SleepCheckNow <{sender_email}>"
    )

    # The actual message header and the SES
    # destination both address the support mailbox.
    message["To"] = ADMIN_AGREEMENT_EMAIL

    message["Subject"] = (
        "Signed Patient Agreement - "
        f"Order {order_number}"
    )

    message.set_content(
        "Home Sleep Health\n\n"
        "The signed Patient Consent, Terms of Service "
        "and Release agreement is attached "
        "for our records.\n\n"
        f"Patient: {patient_name}\n"
        f"Order reference: {order_number}\n\n"
        "Please retain the attached PDF "
        "with the business records.\n\n"
        "This is an automated internal notification."
    )

    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=(
            f"{order_number}-signed-agreement.pdf"
        ),
    )

    result = ses.send_raw_email(
        Source=sender_email,
        Destinations=[
            ADMIN_AGREEMENT_EMAIL
        ],
        RawMessage={
            "Data": message.as_bytes()
        },
        ConfigurationSetName=SES_CONFIGURATION_SET,
    )

    return {
        "message_id": result["MessageId"],
        "recipient": ADMIN_AGREEMENT_EMAIL,
        "admin_recipient": ADMIN_AGREEMENT_EMAIL,
    }