import os
import textract
import fitz  # PyMuPDF
from docx import Document

def extract_text_from_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.docx':
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext == '.pdf':
        with fitz.open(file_path) as pdf:
            return "\n".join([page.get_text() for page in pdf])
    elif ext == '.doc':
        return textract.process(file_path).decode('utf-8')
    else:
        raise ValueError("Unsupported file type")
