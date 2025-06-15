from fastapi import APIRouter, HTTPException, Depends, status
from app.database import get_db
from app.models.document import Document
import os
import logging
from sqlalchemy.orm import Session
from pydantic import BaseModel
import shutil
from app.routes.auth import get_current_user
from app.models.user import User
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
UPLOAD_DIR = "uploaded_files"  # Same upload directory as in other routes
router = APIRouter()

class DeleteRequest(BaseModel):
    filename: str

@router.delete("/documents/{filename}")
def delete_document(
    filename: str, 
    document_id: str = None,
    db: Session = Depends(get_db)
):
    """Delete a document from the database and file system"""
    # Find the document in the database
    document = db.query(Document).filter(Document.filename == filename).first()
    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document {filename} not found"
        )

    try:
        # Delete the file if it exists
        if os.path.exists(document.path):
            os.remove(document.path)
            
            # Check if the user's folder is empty after file deletion
            user_folder = os.path.dirname(document.path)
            if os.path.exists(user_folder) and not os.listdir(user_folder):
                # Remove the empty user folder
                shutil.rmtree(user_folder)

        # Delete from database
        db.delete(document)
        db.commit()
        
        return {"message": "Document deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting document: {str(e)}"
        )

@router.post("/delete-document")
def delete_document_body(request: DeleteRequest, db: Session = Depends(get_db)):
    """Alternative endpoint that accepts a request body with filename"""
    return delete_document(request.filename, db)



@router.delete("/delete/my-account")
async def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Allows an authenticated user to delete their own account.
    This will also delete all documents and associated vector stores for that user.
    """
    user_id = current_user.id
    logger.info(f"User {user_id} attempting to delete their account.")

    try:
        # 1. Delete documents and their associated files/vector stores
        documents = db.query(Document).filter(Document.user_id == user_id).all()
        for doc in documents:
            # Delete file from file system
            if os.path.exists(doc.path):
                os.remove(doc.path)
                logger.info(f"Deleted document file: {doc.path}")
            
            # Delete associated vector store directory
            if doc.file_hash: # Assuming file_hash is used for vector store naming
                vector_store_path = os.path.join(VECTOR_STORE_DIR, doc.file_hash)
                if os.path.exists(vector_store_path):
                    shutil.rmtree(vector_store_path)
                    logger.info(f"Deleted vector store directory: {vector_store_path}")

            # Delete document from database
            db.delete(doc)
            logger.info(f"Deleted document record from DB: {doc.filename} (ID: {doc.id})")
        
        # 2. Delete the user's main upload folder if it becomes empty
        user_upload_dir = os.path.join(UPLOAD_DIR, str(user_id))
        if os.path.exists(user_upload_dir) and not os.listdir(user_upload_dir):
            shutil.rmtree(user_upload_dir)
            logger.info(f"Deleted empty user upload directory: {user_upload_dir}")

        # 3. Delete the user record from the database
        db.delete(current_user)
        db.commit()
        logger.info(f"Account for user ID {user_id} successfully deleted.")

        return {"message": "Account and all associated data deleted successfully"}

    except Exception as e:
        db.rollback() # Rollback any changes if an error occurs
        logger.error(f"Error deleting account for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account due to an internal error: {str(e)}"
        )