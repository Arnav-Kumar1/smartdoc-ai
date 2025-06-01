from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.models.document import Document
from app.database import get_db as get_session
from uuid import UUID
from app.routes.auth import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/documents")
def get_all_documents(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # Filter documents by user_id and sort by upload_time descending
    documents = session.exec(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.upload_time.desc())
    ).all()
    return documents

@router.get("/documents/{document_id}")
def get_document(
    document_id: UUID, 
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if the document belongs to the current user
    if document.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this document")
    
    return document
