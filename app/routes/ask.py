from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import logging

from app.database import get_db
from app.routes.auth import get_current_user
from app.models.user import User # Ensure User model is imported
from app.models.document import Document
from app.config import VECTOR_STORE_DIR

from app.utils.qa_utils import (
    load_vector_store,
    get_llm, # This function now expects 'api_key'
    run_qa_chain,
    rewrite_queries,
    retrieve_top_k_chunks
)

class QAModel(BaseModel):
    filename: str
    question: str

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/ask/test")
async def test_ask_endpoint():
    return {"status": "Ask endpoint is working"}

@router.post("/ask")
async def qa_query(payload: QAModel, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Handles a Q&A query against a vectorized document for the current user,
    using their provided Gemini API key.
    """
    logger.info(f"Received ask request with payload: {payload}")
    logger.info(f"Current user ID: {current_user.id}")
    
    document = db.query(Document).filter(
        Document.filename == payload.filename, 
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found in database")

    # The existing check for is_vectorized and file_hash is good.
    if not document.is_vectorized or not document.file_hash:
        raise HTTPException(status_code=400, detail="Document is not properly vectorized. Please re-vectorize.")

    vector_store_path = os.path.join(VECTOR_STORE_DIR, document.file_hash)

    # NEW: Retrieve the user's Gemini API key from the current_user object
    user_gemini_api_key = current_user.gemini_api_key
    
    # Add a robust check for the API key before proceeding
    if not user_gemini_api_key or user_gemini_api_key.strip() == "":
        logger.error("Gemini API key is missing or empty for the current user during Q&A.")
        raise HTTPException(
            status_code=400, 
            detail="Gemini API key not found for user. Please ensure it is provided during signup."
        )

    try:
        # Load TF-IDF vector store
        vector_store = load_vector_store(vector_store_path)
        
        # FIX: Pass the user's API key to get_llm
        llm = get_llm(api_key=user_gemini_api_key)

        # Expand the question semantically
        rewritten_queries = rewrite_queries(llm, payload.question, num_rephrasals=4)
        combined_query = " OR ".join(rewritten_queries)

        # Retrieve top-k matching chunks
        top_chunks = retrieve_top_k_chunks(vector_store, combined_query)

        # Generate answer using Gemini
        answer, sources = run_qa_chain(llm, payload.question, top_chunks)

        return {
            "original_question": payload.question,
            "rewritten_questions": rewritten_queries,
            "answer": answer,
            "sources": sources
        }

    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except RuntimeError as e:
        logger.error(f"Q&A failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Q&A failed: {str(e)}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during Q&A: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
