from fastapi import APIRouter, HTTPException, Depends, status # Import status for better HTTP codes
from app.utils.extractor import extract_text_from_pdf, extract_text_from_docx
import google.generativeai as genai 
from app.database import get_db
from app.models.document import Document
import os, mimetypes
from sqlalchemy.orm import Session
from app.utils.hierarchical_summarizer import HierarchicalSummarizer
import logging
from app.routes.auth import get_current_user
from app.models.user import User
import google.api_core.exceptions as gcp_exceptions # NEW: Import specific Google Cloud exceptionspydantic
from pydantic import BaseModel
# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploaded_files"
router = APIRouter()

@router.post("/summarize/{filename}")
def summarize_file(filename: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Summarizes a document for the current user using their provided Gemini API key.
    """
    document = db.query(Document).filter(Document.filename == filename, Document.user_id == current_user.id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in DB")

    # Ensure document is vectorized before summarization
    if not document.is_vectorized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document must be vectorized before summarization.")

    # Calculate and set file hash if not already set (important for shared summaries)
    if not document.file_hash:
        file_path = document.path
        if not os.path.exists(file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found at path: {file_path}")
        import hashlib
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            file_hash = hashlib.md5(file_bytes).hexdigest()
        document.file_hash = file_hash
        db.commit()
    else:
        file_hash = document.file_hash # Assign file_hash from document if it already exists
        file_path = document.path

    # If this document already has a summary for this user, return it
    if document.summary:
        return {
            "filename": filename,
            "summary": document.summary,
            "message": "Summary already generated by you, fetched from database"
        }

    # Check for existing summary by file_hash (e.g., another user summarized the same file)
    existing_summary_doc = db.query(Document).filter(
        Document.file_hash == file_hash,
        Document.summary != None
    ).first()
    if existing_summary_doc and existing_summary_doc.summary:
        document.summary = existing_summary_doc.summary
        db.commit()
        msg = "Summary already generated by you, fetched from database" if existing_summary_doc.user_id == current_user.id else "Summary already generated by another user, fetched from database"
        return {
            "filename": filename,
            "summary": document.summary,
            "message": msg
        }

    # Retrieve the user's Gemini API key from the current_user object
    user_gemini_api_key = current_user.gemini_api_key
    
    if not user_gemini_api_key or user_gemini_api_key.strip() == "":
        logger.error("Gemini API key is missing or empty for the current user.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Gemini API key not found for user. Please ensure it is provided during signup."
        )

    logger.info(f"➡️ Requested file for summarization: {file_path}")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found at path: {file_path}")

    mime_type, _ = mimetypes.guess_type(file_path)
    logger.info(f"📦 MIME type: {mime_type}")

    try:
        if mime_type == "application/pdf":
            text = extract_text_from_pdf(file_path)
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text = extract_text_from_docx(file_path)
        elif mime_type == "text/plain":
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")
    except Exception as extract_err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Text extraction error: {str(extract_err)}")

    if not text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Extracted text is empty")

    doc_size_kb = len(text) / 1024
    MAX_DOC_SIZE_KB = 1000
    
    if doc_size_kb > MAX_DOC_SIZE_KB:
        logger.warning(f"⚠️ Document too large ({doc_size_kb:.2f}KB) - skipping API processing")
        
        placeholder_summary = (

            f"This document is too large to summarize due to current API usage limitations. "
            f"To ensure a smooth and reliable experience for all users, we've placed a processing limit "
            f"on very large documents.\n\n"
            f"The extracted plain text from your document is approximately {int(doc_size_kb)}KB — "
            f"this size is calculated *after* removing all formatting (like layout, fonts, or embedded elements), "
            f"leaving only the raw text content.\n\n"
            f"For reference, {MAX_DOC_SIZE_KB}KB of raw text represents a very large amount of content "
            f"and typically corresponds to over five-hundreds pages of plain text at Times New Roman, 12 pt). Please try uploading a smaller document"
        )

        document.summary = placeholder_summary
        db.commit()
        
        return {
            "filename": filename,
            "summary": placeholder_summary,
            "message": "Document too large to summarize with current API quota",
            "document_size_kb": round(doc_size_kb, 2)
        }

    try:
        summarizer = HierarchicalSummarizer(
            model_name="gemini-1.5-flash-latest",
            temperature=0.1,
            max_tokens_per_chunk=4000,
            chunk_overlap=400,
            max_retries=3,
            api_key=user_gemini_api_key
        )
        
        result = summarizer.summarize(text)
        final_summary = result["summary"]
        
        logger.info("✅ Summary complete.")
        logger.info(f"📊 Used {result['api_calls']} API calls for {result['sections_used']} sections")
        
        document.summary = final_summary
        db.commit()
        
        return {
            "filename": filename,
            "summary": final_summary,
            "sections_used": result["sections_used"],
            "batches_used": result["batches_used"],
            "api_calls": result["api_calls"]
        }
    except gcp_exceptions.ResourceExhausted as re: # NEW: Catch specific quota error
        logger.error(f"⚠️ Summarization failed due to quota exhaustion: {str(re)}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, # Use 429 for quota errors
            detail=(
                "Summarization failed due to API quota limits. "
                "Please try again later or with a smaller document. "
                "If the issue persists, contact support."
            )
        )
    except Exception as e: # Catch other general exceptions
        logger.error(f"⚠️ Summarization failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Summarization failed: {str(e)}")

class SummarizeRequest(BaseModel):
    filename: str

@router.post("/summarize")
def summarize_file_body(request: SummarizeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return summarize_file(request.filename, db, current_user)
