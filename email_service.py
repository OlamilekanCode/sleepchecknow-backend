import boto3
from email.message import EmailMessage


ses = boto3.client("ses")


def send_agreement_email(
    recipient_email: str,
    pdf_bytes: bytes,
    order_number: str,
    sender_email: str,
):
    message = EmailMessage()

    message["Subject"] = f"Your SleepCheckNow Signed Agreement - {order_number}"
    message["From"] = sender_email
    message["To"] = recipient_email

    message.set_content(
        "Thank you for your order.\n\n"
        "Attached is a copy of your signed Patient Consent, "
        "Terms of Service & Release agreement.\n\n"
        "SleepCheckNow / Home Sleep Health"
    )

    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=f"{order_number}-signed-agreement.pdf",
    )

    return ses.send_raw_email(
        Source=sender_email,
        Destinations=[recipient_email],
        RawMessage={
            "Data": message.as_bytes()
        },
    )