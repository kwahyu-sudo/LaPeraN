import pdfplumber


def extract_text_from_pdf(pdf_path: str) -> str:
    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if text:
                full_text.append(f"--- Halaman {i+1} ---\n{text}")
    return "\n\n".join(full_text)


def is_pdf_readable(pdf_path: str) -> bool:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:2]:
            if page.extract_text():
                return True
    return False
