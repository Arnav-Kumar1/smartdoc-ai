import os
import logging
import traceback
import hashlib

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
from typing import List

from sentence_transformers import SentenceTransformer
import numpy as np

router = APIRouter()

# Global variable for lazy loading the model
_embedding_model = None

def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        logging.info("[VECTORIZE] Loading smaller embedding model: paraphrase-MiniLM-L3-v2")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        logging.info("[VECTORIZE] Embedding model loaded")
    return _embedding_model

def batch_embed_texts(texts: List[str], batch_size: int = 16) -> List[np.ndarray]:
    model = get_embedding_model()
    embeddings = []
    logging.info(f"[VECTORIZE] Generating embeddings in batches of size {batch_size}...")
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        logging.info(f"[VECTORIZE] Embedding batch {i // batch_size + 1} / {((len(texts)-1)//batch_size)+1}")
        emb_batch = model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        embeddings.extend(emb_batch)
    return embeddings

@router.post("/vectorize/{filename}")
async def vectorize_document(filename: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        logging.info(f"[VECTORIZE] Starting vectorization for: {filename}")

        document = db.query(Document).filter(Document.filename == filename, Document.user_id == current_user.id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found in database")

        if not os.path.exists(document.path):
            raise HTTPException(status_code=404, detail=f"Document file not found at {document.path}")

        # Compute file hash if missing
        if not document.file_hash:
            logging.info("[VECTORIZE] Computing file hash...")
            with open(document.path, "rb") as f:
                file_bytes = f.read()
                document.file_hash = hashlib.md5(file_bytes).hexdigest()
            db.commit()

        # Check if any document with same hash is already vectorized
        existing_vectorized = db.query(Document).filter(
            Document.file_hash == document.file_hash,
            Document.is_vectorized == True
        ).first()

        if existing_vectorized:
            if not document.is_vectorized:
                document.is_vectorized = True
                db.commit()
            msg = ("already vectorized by you, marked as vectorized"
                   if existing_vectorized.user_id == current_user.id else
                   "already vectorized by another user, marked as vectorized")
            logging.info(f"[VECTORIZE] {msg}")
            return {"message": msg}

        if document.is_vectorized:
            logging.info("[VECTORIZE] Document already vectorized by this user")
            return {"message": "Document already vectorized", "filename": filename}

        vector_store_path = os.path.join(VECTOR_STORE_DIR, document.file_hash)
        os.makedirs(vector_store_path, exist_ok=True)

        # Text extraction
        try:
            if filename.lower().endswith('.pdf'):
                logging.info("[VECTORIZE] Extracting text from PDF")
                text = extract_text_from_pdf(document.path)
            elif filename.lower().endswith('.docx'):
                logging.info("[VECTORIZE] Extracting text from DOCX")
                text = extract_text_from_docx(document.path)
            else:
                logging.info("[VECTORIZE] Extracting plain text")
                with open(document.path, 'r', encoding='utf-8') as f:
                    text = f.read()
        except Exception:
            logging.error("[VECTORIZE] Text extraction failed")
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=400, detail="Text extraction error")

        # Text splitting
        try:
            logging.info("[VECTORIZE] Splitting text into chunks")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            texts = text_splitter.split_text(text)
            metadatas = [{"chunk_id": idx} for idx in range(len(texts))]
        except Exception:
            logging.error("[VECTORIZE] Text splitting failed")
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail="Text splitting error")

        # Generate embeddings in batches
        try:
            embeddings = batch_embed_texts(texts, batch_size=16)
            logging.info("[VECTORIZE] Embeddings generated for all chunks")

            # Build FAISS index from embeddings manually
            vector_db = FAISS.from_embeddings(
                embeddings=embeddings,
                metadatas=metadatas
            )
            logging.info("[VECTORIZE] FAISS vector store created")

            vector_db.save_local(vector_store_path)
            logging.info(f"[VECTORIZE] FAISS vector store saved at {vector_store_path}")

        except Exception:
            logging.error("[VECTORIZE] Embedding or vector store creation failed")
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail="Vector store creation failed")

        # Update DB status
        try:
            document.is_vectorized = True
            db.commit()
            logging.info("[VECTORIZE] Document vectorized and DB updated successfully")
            return {"message": "Document vectorized successfully", "filename": filename}
        except Exception:
            logging.error("[VECTORIZE] Failed to update DB after vectorization")
            logging.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail="DB update failed after vectorization")

    except Exception:
        logging.critical("[VECTORIZE] Unexpected error during vectorization")
        logging.critical(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Unexpected error during vectorization")
