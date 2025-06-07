from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from pydantic import BaseModel
import os
from app.routes.auth import get_current_user
from app.models.user import User
from sqlalchemy.orm import Session
from app.models.document import Document
import logging
from app.config import VECTOR_STORE_DIR

from app.utils.qa_utils import (
    load_vector_store,
    setup_retriever,
    get_llm,
    build_qa_chain,
    run_qa_chain,
    rewrite_queries
)

class QAModel(BaseModel):
    filename: str
    question: str

# Add this at the top after imports
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
    
    # First, get the document from the database to find its file_hash
    document = db.query(Document).filter(
        Document.filename == payload.filename, 
        Document.user_id == current_user.id
    ).first()
    
    logger.info(f"Looking for document with filename: {payload.filename}")
    logger.info(f"Found document: {document}")
    
    if not document:
        logger.error(f"Document not found: filename={payload.filename}, user_id={current_user.id}")
        raise HTTPException(status_code=404, detail="Document not found in database")
    
    if not document.is_vectorized:
        raise HTTPException(status_code=400, detail="Document is not vectorized yet. Please vectorize it first.")
    
    if not document.file_hash:
        raise HTTPException(status_code=400, detail="Document hash not found. Please re-vectorize the document.")
    
    # Use the file_hash to locate the vector store
    # Update vector store path to use config path
    vector_store_path = os.path.join(VECTOR_STORE_DIR, document.file_hash)

    try:
        vector_store = load_vector_store(vector_store_path)  # Now matches signature
        retriever = setup_retriever(vector_store)
        llm = get_llm()

        # Call rewrite_queries once to get a list: original + 4 rephrasals
        rewritten_queries = rewrite_queries(llm, payload.question, num_rephrasals=4)

        # Combine all queries (list of strings) with " OR "
        combined_query = " OR ".join(rewritten_queries)

        qa_chain = build_qa_chain(llm, retriever)
        answer, sources = run_qa_chain(qa_chain, combined_query)

        return {
            "original_question": payload.question,
            "rewritten_questions": rewritten_queries,
            "answer": answer,
            "sources": sources
        }

    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    try:
        answer, sources = process_qa_request(
            document_id=document.id,
            query=payload.question,
            filename=document.filename,
            file_hash=document.file_hash
        )
        return {"answer": answer, "sources": sources}
    except RuntimeError as e:
        logger.error(f"Q&A failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Q&A failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Q&A failed: {str(e)}"
        )
