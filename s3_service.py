import boto3

BUCKET = "sleepchecknow-signed-agreements"
TEMPLATE_KEY = "templates/patient-consent-v1.pdf"

s3 = boto3.client("s3")


def get_template():
    response = s3.get_object(
        Bucket=BUCKET,
        Key=TEMPLATE_KEY,
    )

    return response["Body"].read()


def save_signed_pdf(pdf_bytes, order_number):
    key = f"signed/{order_number}-signed-agreement.pdf"

    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
    )

    return key