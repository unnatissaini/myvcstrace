# utils/file_parser.py

import os
import textract
import fitz  # PyMuPDF
from docx import Document

def extract_text_from_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.docx':
        return extract_docx(file_path)
    elif ext == '.doc':
        return extract_doc(file_path)
    elif ext == '.pdf':
        return extract_pdf(file_path)
    else:
        raise ValueError("Unsupported file type")

def extract_docx(file_path: str) -> str:
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_doc(file_path: str) -> str:
    # Works for .doc (binary) using textract
    return textract.process(file_path).decode('utf-8')

def extract_pdf(file_path: str) -> str:
    text = ""
    with fitz.open(file_path) as pdf:
        for page in pdf:
            text += page.get_text()
    return text
