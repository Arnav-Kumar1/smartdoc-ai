import os
import hashlib
import joblib
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from app.database import get_db
from app.models.document import Document
from app.routes.auth import get_current_user
from app.models.user import User
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.utils.extractor import extract_text_from_pdf, extract_text_from_docx
from app.config import VECTOR_STORE_DIR
from sklearn.feature_extraction.text import TfidfVectorizer

# Initialize the FastAPI Router
router = APIRouter()

@router.post("/vectorize/{filename}")
async def vectorize_document(filename: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    document = db.query(Document).filter(Document.filename == filename, Document.user_id == current_user.id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found in database")

    document_path = document.path
    if not os.path.exists(document_path):
        raise HTTPException(status_code=404, detail=f"Document file not found at {document_path}")

    # Calculate file hash if not already set
    if not document.file_hash:
        with open(document_path, "rb") as f:
            file_bytes = f.read()
            file_hash = hashlib.md5(file_bytes).hexdigest()
        document.file_hash = file_hash
        db.commit()
    else:
        file_hash = document.file_hash

    # Check for existing vectorized file
    existing_vectorized = db.query(Document).filter(
        Document.file_hash == file_hash,
        Document.is_vectorized == True
    ).first()

    if existing_vectorized:
        if not document.is_vectorized:
            document.is_vectorized = True
            db.commit()
        msg = "already vectorized by you, marked as vectorized" if existing_vectorized.user_id == current_user.id else "already vectorized by another user, marked as vectorized"
        return {"message": msg}

    if document.is_vectorized:
        return {"message": "Document already vectorized", "filename": filename}

    # Create vector store path
    vector_store_path = os.path.join(VECTOR_STORE_DIR, file_hash)
    os.makedirs(vector_store_path, exist_ok=True)

    # Extract text
    if filename.lower().endswith('.pdf'):
        text = extract_text_from_pdf(document_path)
    elif filename.lower().endswith('.docx'):
        text = extract_text_from_docx(document_path)
    else:
        try:
            with open(document_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except:
            raise HTTPException(status_code=400, detail="Unsupported file type")

    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_text(text)

    if not chunks:
        raise HTTPException(status_code=400, detail="No text chunks could be extracted.")

    # TF-IDF vectorization
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(chunks)

    # Save all components
    joblib.dump(vectorizer, os.path.join(vector_store_path, "vectorizer.pkl"))
    joblib.dump(tfidf_matrix, os.path.join(vector_store_path, "matrix.pkl"))
    joblib.dump(chunks, os.path.join(vector_store_path, "chunks.pkl"))

    # Mark document as vectorized
    document.is_vectorized = True
    db.commit()

    return {"message": "Document vectorized successfully", "filename": filename}
