import pdfplumber
import re
import io


# def extract_text_from_pdf(file_bytes: bytes) -> str:
#     """Extract all text from a PDF file given its raw bytes."""
#     import io
#     text_parts = []

#     with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
#         for page in pdf.pages:
#             text = page.extract_text()
#             if text:
#                 text_parts.append(text)

#     return "\n\n".join(text_parts)

def clean_extracted_text(text: str) -> str:
    # Fix words merged without spaces (lowercase letter immediately followed by uppercase)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # Normalise multiple spaces
    text = re.sub(r' +', ' ', text)
    return text.strip()


# def extract_text_from_pdf(file_bytes: bytes) -> str:
#     text_parts = []

#     with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
#         for page in pdf.pages:
#             text = page.extract_text()
#             if text:
#                 text_parts.append(text)

#     raw_text = "\n\n".join(text_parts)
#     return clean_extracted_text(raw_text)

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text_parts = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text(layout=True)
            if text:
                text_parts.append(text)

    raw_text = "\n\n".join(text_parts)
    return clean_extracted_text(raw_text)