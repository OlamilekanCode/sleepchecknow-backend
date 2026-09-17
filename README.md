# SleepCheckNow Agreement Backend

Backend service for generating, storing, and delivering signed patient consent agreements for SleepCheckNow orders.

The service is designed to work with the existing Webflow checkout flow. After a customer accepts the consent agreement and completes an order, the backend generates a personalized PDF containing the customer's electronic signature and order information.

## Current Flow

```text
Webflow Checkout
      ↓
Consent accepted + legal name captured
      ↓
Order completed
      ↓
AWS Lambda
      ↓
Load agreement template from S3
      ↓
Generate signed PDF
      ↓
Store completed agreement in S3
      ↓
Send agreement email
````

## Stack

* Python
* AWS Lambda
* Amazon S3
* Amazon SES
* API Gateway
* `pypdf`
* `reportlab`
* GitHub Actions
* GitHub OIDC for AWS deployment

## AWS Resources

* `SleepCheckNow-AgreementProcessor` — Lambda function
* `SleepCheckNow-LambdaExecutionRole` — Lambda IAM role
* `sleepchecknow-signed-agreements` — private S3 bucket

S3 structure:

```text
sleepchecknow-signed-agreements/
├── templates/
│   └── patient-consent-v1.pdf
└── signed/
    └── <order-number>-signed-agreement.pdf
```

## Project Structure

```text
.
├── .github/
│   └── workflows/
│       └── deploy.yml
├── assets/
│   └── patient-consent-v1.pdf
├── email_service.py
├── lambda_function.py
├── pdf_service.py
├── s3_service.py
├── requirements.txt
└── README.md
```

## PDF Generation

The original consent agreement is stored as a master PDF template.

For each completed order, the backend adds:

* Customer full legal name
* Electronic signature
* Signing date
* Order / transaction number

The completed agreement is then saved as a new PDF without modifying the original template.

## Local Setup

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Deployment

Deployment is handled through GitHub Actions.

A push to the `main` branch builds the Lambda deployment package and updates:

```text
SleepCheckNow-AgreementProcessor
```

AWS authentication is handled using GitHub OIDC rather than permanent AWS access keys.

## Security

* Signed agreements are stored in a private S3 bucket.
* Public S3 access is disabled.
* S3 versioning is enabled.
* AWS permissions are scoped to SleepCheckNow resources.
* Patient/order payloads should not be written to application logs.
* AWS services handling protected information must remain within the HIPAA-eligible AWS environment configured for the project.

## Current Status

Working:

* Consent PDF template
* Dynamic PDF generation
* Electronic signature placement
* S3 template storage
* S3 signed-agreement storage logic
* Lambda processing logic
* GitHub deployment workflow

Still being integrated:

* GitHub → AWS OIDC deployment role
* Webflow order webhook
* API Gateway endpoint
* SES domain verification
* Customer agreement email
* Business agreement email
* Full end-to-end order testing

## License

Private project for SleepCheckNow / Home Sleep Health.