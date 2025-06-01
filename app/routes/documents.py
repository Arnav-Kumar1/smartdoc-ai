@router.get("/documents")
def get_user_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    documents = db.query(Document).filter(Document.user_id == current_user.id).all()
    return [
        {
            "id": str(doc.id),
            "filename": doc.filename,
            "file_type": doc.file_type,
            "upload_time": doc.upload_time.isoformat(),
            "summary": doc.summary,
            "is_vectorized": doc.is_vectorized,  # Include vectorization status
            "user_id": str(doc.user_id)  # Make sure user_id is included
        }
        for doc in documents
    ]