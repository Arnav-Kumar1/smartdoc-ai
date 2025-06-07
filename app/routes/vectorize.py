import os
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from app.database import get_db
from app.models.document import Document
from app.routes.auth import get_current_user
from app.models.user import User
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.utils.extractor import extract_text_from_pdf, extract_text_from_docx
from app.config import VECTOR_STORE_DIR
from app.model_loader import get_embedding_model

router = APIRouter()

@router.post("/vectorize/{filename}")
async def vectorize_document(
    filename: str, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user),
    embeddings = Depends(get_embedding_model)  # Correct dependency injection
):
    document = db.query(Document).filter(
        Document.filename == filename, 
        Document.user_id == current_user.id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found in database")
    
    document_path = document.path
    if not os.path.exists(document_path):
        raise HTTPException(status_code=404, detail=f"Document file not found at {document_path}")

    # Calculate file hash if not already set
    if not document.file_hash:
        import hashlib
        with open(document_path, "rb") as f:
            file_bytes = f.read()
            file_hash = hashlib.md5(file_bytes).hexdigest()
        document.file_hash = file_hash
        db.commit()
    else:
        file_hash = document.file_hash

    # Check if any document with the same hash has already been vectorized
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
        print("[DEBUG] Returning: already vectorized by this user")
        return {"message": "Document already vectorized", "filename": filename}
    
    # Define the vector store path using the file hash for consistency
    vector_store_path = os.path.join(VECTOR_STORE_DIR, file_hash)
    os.makedirs(vector_store_path, exist_ok=True)
    
    # Extract text from the document
    if filename.lower().endswith('.pdf'):
        print("[DEBUG] Extracting text from PDF")
        text = extract_text_from_pdf(document_path)
    elif filename.lower().endswith('.docx'):
        print("[DEBUG] Extracting text from DOCX")
        text = extract_text_from_docx(document_path)
    else:
        # Try to handle text files or other formats
        try:
            print("[DEBUG] Extracting text from TXT or other format")
            with open(document_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except:
            print("[DEBUG] Unsupported file type")
            raise HTTPException(status_code=400, detail="Unsupported file type")

    # Split the document text
    print("[DEBUG] Splitting document text")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_text(text)

    # Add chunk metadata
    metadatas = [{"chunk_id": idx} for idx in range(len(texts))]

    # Create FAISS vector store using the pre-loaded embeddings
    print("[DEBUG] Creating FAISS vector store")
    vector_db = FAISS.from_texts(
        texts=texts, 
        embedding=embeddings,  # Use the injected embeddings
        metadatas=metadatas
    )

    # Save the FAISS vector store
    print("[DEBUG] Saving FAISS vector store")
    vector_db.save_local(vector_store_path)

    # Update document in database
    document.is_vectorized = True
    document.file_hash = file_hash
    db.commit()
    print("[DEBUG] Returning: Document vectorized successfully")

    return {"message": "Document vectorized successfully", "filename": filename}