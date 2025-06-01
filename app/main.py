from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from app.database import create_db
from app.routes import file_info, upload, summarize, vectorize, ask, delete, health, auth,admin
from app.config import create_required_directories

app = FastAPI(title="SmartDoc AI API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create database tables on startup
from app.config import create_required_directories

@app.on_event("startup")
def on_startup():
    create_required_directories()  # Create all directories in the correct location
    create_db()

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

@app.get("/")
def read_root():
    return {"message": "Welcome to SmartDoc AI API"}