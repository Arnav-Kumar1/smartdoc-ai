import fitz  # PyMuPDF

def extract_text_from_pdf(file_path: str) -> str:
    full_text = []
    with fitz.open(file_path) as doc:
        for page in doc:
            full_text.append(page.get_text())
    return "\n".join(full_text)


from docx import Document

def extract_text_from_docx(file_path: str) -> str:
    try:
        doc = Document(file_path)
        full_text = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n".join(full_text)
    except Exception as e:
        raise ValueError(f"Error while extracting DOCX: {str(e)}")
