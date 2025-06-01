from fastapi import APIRouter, HTTPException, Depends, status
from app.database import get_db
from app.models.document import Document
import os
from sqlalchemy.orm import Session
from pydantic import BaseModel
import shutil

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

