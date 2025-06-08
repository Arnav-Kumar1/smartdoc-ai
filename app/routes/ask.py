from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import logging

from app.database import get_db
from app.routes.auth import get_current_user
from app.models.user import User
from app.models.document import Document
from app.config import VECTOR_STORE_DIR

from app.utils.qa_utils import (
    load_vector_store,
    get_llm,
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
    logger.info(f"Received ask request with payload: {payload}")
    logger.info(f"Current user ID: {current_user.id}")
    
    document = db.query(Document).filter(
        Document.filename == payload.filename, 
        Document.user_id == current_user.id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found in database")

    if not document.is_vectorized or not document.file_hash:
        raise HTTPException(status_code=400, detail="Document is not properly vectorized. Please re-vectorize.")

    vector_store_path = os.path.join(VECTOR_STORE_DIR, document.file_hash)

    try:
        # Load TF-IDF vector store
        vector_store = load_vector_store(vector_store_path)
        llm = get_llm()

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
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Q&A failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Q&A failed: {str(e)}")
