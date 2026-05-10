from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import os

def create_3c_certificate():
    filename = "test_pdfs/3c_cert_sample.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 30*mm, "CCC CERTIFICATE")
    c.drawCentredString(width/2, height - 38*mm, "中国国家强制性产品认证证书")
    
    c.setFont("Helvetica", 12)
    y = height - 60*mm
    
    data = [
        ("Certificate No:", "2023012201001234"),
        ("Product Name:", "Lithium-ion Battery Pack"),
        ("Product Model:", "LP-48V-100Ah"),
        ("Manufacturer:", "Shenzhen PowerTech Co., Ltd."),
        ("Factory Address:", "Building 5, Tech Park, Nanshan District, Shenzhen"),
        ("Issuing Authority:", "China Quality Certification Centre (CQC)"),
        ("Issue Date:", "2023-01-15"),
        ("Valid Until:", "2028-01-14"),
        ("Certification Type:", "CCC (China Compulsory Certification)"),
        ("Standards:", "GB 31241-2014, GB/T 36275-2018"),
    ]
    
    for label, value in data:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(30*mm, y, label)
        c.setFont("Helvetica", 11)
        c.drawString(80*mm, y, value)
        y -= 8*mm
    
    c.save()
    print(f"Created: {filename}")

def create_ce_certificate():
    filename = "test_pdfs/ce_cert_sample.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height - 25*mm, "EU DECLARATION OF CONFORMITY")
    
    c.setFont("Helvetica", 11)
    y = height - 50*mm
    
    text_lines = [
        "Product: Wireless Bluetooth Headphones",
        "Model: BT-Pro-2023",
        "",
        "Manufacturer: Berlin Audio GmbH",
        "Address: Friedrichstraße 123, 10117 Berlin, Germany",
        "",
        "We declare that the above product complies with:",
        "• EU Directive 2014/53/EU (RED Directive)",
        "• EU Directive 2011/65/EU (RoHS Directive)",
        "• EN 300 328 V2.2.2",
        "• EN 301 489-1 V2.2.3",
        "",
        "CE Marking: Yes",
        "Notified Body: TÜV SÜD Product Service GmbH",
        "Certificate Number: CE-2023-DE-45678",
        "Issue Date: 15 March 2023",
        "",
        "Authorized Signature:",
        "_____________________",
        "Dr. Hans Mueller, Technical Director",
        "Date: 2023-03-15"
    ]
    
    for line in text_lines:
        c.drawString(30*mm, y, line)
        y -= 7*mm
    
    c.save()
    print(f"Created: {filename}")

def create_fcc_certificate():
    filename = "test_pdfs/fcc_cert_sample.pdf"
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 25*mm, "FCC CERTIFICATION")
    c.drawCentredString(width/2, height - 32*mm, "Federal Communications Commission")
    
    c.setFont("Helvetica", 11)
    y = height - 55*mm
    
    data = [
        "FCC ID: 2ABCD-XYZ123",
        "",
        "Grantee: Silicon Valley Electronics Inc.",
        "Product: Smart Home Gateway",
        "Model: SHG-5000",
        "",
        "Equipment Authorization: Supplier's Declaration of Conformity (SDoC)",
        "",
        "This device complies with Part 15 of the FCC Rules:",
        "• Operation is subject to the following two conditions:",
        "  (1) This device may not cause harmful interference.",
        "  (2) This device must accept any interference received.",
        "",
        "Test Standards:",
        "• FCC Part 15, Subpart B (Class B digital device)",
        "• ANSI C63.4-2014",
        "",
        "Issue Date: June 20, 2023",
        "Test Report: TR-2023-06-001",
        "TCB: National Technical Systems (NTS)"
    ]
    
    for line in data:
        c.drawString(30*mm, y, line)
        y -= 6*mm
    
    c.save()
    print(f"Created: {filename}")

if __name__ == "__main__":
    os.makedirs("test_pdfs", exist_ok=True)
    create_3c_certificate()
    create_ce_certificate()
    create_fcc_certificate()
    print("\nAll test PDFs created successfully!")
