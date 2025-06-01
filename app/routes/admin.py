# app/routes/admin.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.user import User, UserCreate, UserResponse
from app.routes.auth import get_current_user
from typing import List
from app.models.document import Document  # Add this import
from uuid import UUID
import shutil
import os
from app.config import UPLOAD_DIR  # Add this import at the top

# Remove the prefix here since it's already defined in main.py
router = APIRouter(tags=["Admin"])

def verify_admin(current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

@router.get("/users", response_model=List[UserResponse])
async def get_all_users(
    current_user: User = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return [
        {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at,
            "is_active": bool(user.is_active),  # Include is_active
            "is_admin": bool(user.is_admin)     # Include is_admin
        }
        for user in users
    ]

@router.get("/documents", response_model=List[dict])
async def get_all_documents(
    current_user: User = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Get all documents (admin only)"""
    documents = db.query(Document).all()
    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "file_type": doc.file_type,
            "upload_time": doc.upload_time.isoformat(),
            "summary": doc.summary,
            "is_vectorized": doc.is_vectorized,
            "user_id": str(doc.user_id),
            "path": doc.path
        }
        for doc in documents
    ]

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Delete a document (admin only)"""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete file from filesystem
    if os.path.exists(document.path):
        os.remove(document.path)
    
    # Delete from database
    db.delete(document)
    db.commit()
    return {"message": "Document deleted successfully"}

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Delete a user (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_admin:
        raise HTTPException(status_code=400, detail="Cannot delete admin user")

    try:
        # Delete user's entire upload folder
        user_upload_dir = os.path.join(UPLOAD_DIR, str(user.id))
        if os.path.exists(user_upload_dir):
            shutil.rmtree(user_upload_dir)

        # Delete all documents from database
        db.query(Document).filter(Document.user_id == user.id).delete()
        
        # Delete user
        db.delete(user)
        db.commit()
        
        return {"message": "User and all associated data deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting user: {str(e)}"
        )

@router.post("/bulk-delete/users")
async def bulk_delete_users(
    user_ids: List[UUID],
    current_user: User = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Delete multiple users in bulk (admin only)"""
    deleted_count = 0
    failed_users = []

    for user_id in user_ids:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                failed_users.append(str(user_id))
                continue
                
            # Don't delete admin users
            if user.is_admin:
                failed_users.append(str(user_id))
                continue

            # Delete user's documents
            docs = db.query(Document).filter(Document.user_id == user_id).all()
            for doc in docs:
                if os.path.exists(doc.path):
                    os.remove(doc.path)
                db.delete(doc)

            # Delete user
            db.delete(user)
            deleted_count += 1

        except Exception as e:
            failed_users.append(str(user_id))

    db.commit()
    return {"success_count": deleted_count, "failed_users": failed_users}

@router.post("/bulk-delete/documents")
async def bulk_delete_documents(
    document_ids: List[UUID],
    current_user: User = Depends(verify_admin),
    db: Session = Depends(get_db)
):
    """Delete multiple documents in bulk (admin only)"""
    deleted_count = 0
    failed_documents = []

    for doc_id in document_ids:
        try:
            document = db.query(Document).filter(Document.id == doc_id).first()
            if not document:
                failed_documents.append(str(doc_id))
                continue

            # Delete file from filesystem
            if os.path.exists(document.path):
                os.remove(document.path)

            # Delete from database
            db.delete(document)
            deleted_count += 1

        except Exception as e:
            failed_documents.append(str(doc_id))

    db.commit()
    return {"success_count": deleted_count, "failed_documents": failed_documents}
