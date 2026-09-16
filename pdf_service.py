from io import BytesIO

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas


def generate_pdf(
    template_bytes: bytes,
    full_name: str,
    signature: str,
    signed_date: str,
    order_number: str,
) -> bytes:

    reader = PdfReader(BytesIO(template_bytes))
    writer = PdfWriter()

    packet = BytesIO()
    overlay = canvas.Canvas(packet, pagesize=(612, 792))

    overlay.setFont("Helvetica", 11)
    overlay.drawString(208, 147, full_name)

    overlay.setFont("Courier-Oblique", 12)
    overlay.drawString(141, 120, signature)

    overlay.setFont("Helvetica", 11)
    overlay.drawString(64, 94, signed_date)
    overlay.drawString(173, 67, order_number)

    overlay.save()
    packet.seek(0)

    overlay_page = PdfReader(packet).pages[0]

    writer.add_page(reader.pages[0])
    writer.add_page(reader.pages[1])

    final_page = reader.pages[2]
    final_page.merge_page(overlay_page)
    writer.add_page(final_page)

    output = BytesIO()
    writer.write(output)

    return output.getvalue()