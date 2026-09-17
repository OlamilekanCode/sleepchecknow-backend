import os
import boto3
from email.message import EmailMessage


ses = boto3.client(
    "ses",
    region_name=os.getenv("AWS_REGION", "eu-north-1"),
)


def send_agreement_email(
    recipient_email: str,
    pdf_bytes: bytes,
    order_number: str,
    customer_name: str | None = None,
):
    """
    Sends the customer's signed consent agreement as a PDF attachment.
    """

    sender_email = os.getenv("SES_FROM_EMAIL")

    if not sender_email:
        raise ValueError("SES_FROM_EMAIL environment variable is not configured")

    if not recipient_email:
        raise ValueError("Recipient email is required")

    if not pdf_bytes:
        raise ValueError("PDF content is required")

    display_name = customer_name or "Customer"

    message = EmailMessage()

    message["Subject"] = (
        f"Your SleepCheckNow Signed Agreement - {order_number}"
    )

    message["From"] = f"SleepCheckNow <{sender_email}>"
    message["To"] = recipient_email

    message.set_content(
        f"Hello {display_name},\n\n"
        "Thank you for your order with SleepCheckNow.\n\n"
        "Attached is a copy of your signed Patient Consent, "
        "Terms of Service & Release agreement for your records.\n\n"
        f"Order: {order_number}\n\n"
        "SleepCheckNow / Home Sleep Health\n\n"
        "This is an automated email. Please do not reply."
    )

    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"{order_number}-signed-agreement.pdf",
    )

    response = ses.send_raw_email(
        Source=sender_email,
        Destinations=[recipient_email],
        RawMessage={
            "Data": message.as_bytes()
        },
    )

    return {
        "message_id": response["MessageId"],
        "recipient": recipient_email,
    }