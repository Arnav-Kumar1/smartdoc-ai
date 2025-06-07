from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.database import create_db
from app.routes import file_info, upload, summarize, vectorize, ask, delete, health, auth, admin
from app.config import create_required_directories
from app.model_loader import get_embedding_model, get_summarization_model
import os

# Initialize app
app = FastAPI(
    title="SmartDoc AI API",
    description="API for document processing and AI-powered interactions",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single startup event handler
@app.on_event("startup")
def startup_event():
    """Initialize application resources on startup"""
    print("Starting application initialization...")
    create_required_directories()
    create_db()
    
    # Preload models
    get_embedding_model()  # Load embedding model
    # get_summarization_model()  # Uncomment if needed
    
    print("Application startup complete")

# Include routers
app.include_router(auth.router, tags=["authentication"], prefix="/auth")
app.include_router(file_info.router, tags=["documents"])
app.include_router(upload.router, tags=["documents"])
app.include_router(summarize.router, tags=["documents"])
app.include_router(vectorize.router, tags=["documents"])
app.include_router(ask.router, tags=["chat"])
app.include_router(delete.router, tags=["documents"])
app.include_router(health.router, tags=["system"])
app.include_router(admin.router, tags=["admin"], prefix="/admin")

@app.get("/", include_in_schema=False)
def read_root():
    return {
        "message": "Welcome to SmartDoc AI API",
        "docs": "/docs",
        "redoc": "/redoc"
    }