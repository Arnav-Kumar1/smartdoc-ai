# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import time
from datetime import datetime # Added for datetime.utcnow() (though default_factory handles creation time)

# --- Database Imports ---
from app.database import create_db, engine # engine is needed for session and metadata.create_all
from sqlmodel import Session, SQLModel # Session and SQLModel.metadata are used

# --- Model Imports ---
from app.models.user import User # User model is needed for admin creation

# --- Config Imports ---
from app.config import create_required_directories, DB_DIR # DB_DIR is used in initialize_database_and_admin_user

# --- Router Imports ---
from app.routes import file_info, upload, summarize, vectorize, ask, delete, health, auth, admin

app = FastAPI(title="SmartDoc AI API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Function to initialize database and admin user (Moved from main_utils.py) ---
def initialize_database_and_admin_user():
    print("Attempting to initialize database and admin user...")

    time.sleep(5) # Optional, but can help with file system stability

    db_file_name = "smartdoc.db"
    db_full_path = os.path.join(DB_DIR, db_file_name)
    
    os.makedirs(DB_DIR, exist_ok=True) # Ensure DB directory exists
    print(f"Ensured database directory '{DB_DIR}' exists.")

    admin_email = os.getenv("ADMIN_EMAIL", "arnav9637@gmail.com")
    admin_username = os.getenv("ADMIN_USERNAME", "Initial Admin")
    admin_raw_password = os.getenv("ADMIN_PASSWORD")

    if not admin_raw_password:
        print("WARNING: ADMIN_PASSWORD environment variable not set. Admin user will not be created/updated.")
        print("Please set ADMIN_PASSWORD in your Railway variables.")
        return

    with Session(engine) as db:
        print(f"Checking for admin user with email: {admin_email}")
        existing_admin = db.exec(select(User).where(User.email == admin_email)).first()

        if not existing_admin:
            print(f"Admin user '{admin_email}' not found. Creating new admin user.")
            hashed_password = get_password_hash(admin_raw_password) # Use imported function
            new_admin = User(
                email=admin_email,
                username=admin_username,
                hashed_password=hashed_password,
                is_admin=True,
                is_active=True,
                created_at=datetime.utcnow() # Ensure created_at is handled correctly
            )
            db.add(new_admin)
            db.commit()
            db.refresh(new_admin)
            print(f"Admin user '{admin_email}' created successfully.")
        else:
            print(f"Admin user '{admin_email}' already exists. Ensuring admin privileges and password.")
            
            if not existing_admin.is_admin:
                existing_admin.is_admin = True
                print(f"User '{admin_email}' granted admin privileges.")
            
            # Check if password needs to be updated using the imported verify_password
            if not verify_password(admin_raw_password, existing_admin.hashed_password):
                 print(f"Updating password for admin user '{admin_email}'.")
                 existing_admin.hashed_password = get_password_hash(admin_raw_password) # Use imported function
            
            db.commit()
            db.refresh(existing_admin)
            print(f"Admin user '{admin_email}' state updated.")

    print("Database and admin initialization complete.")

# --- Existing startup event ---
@app.on_event("startup")
def on_startup():
    print("Running startup events...")
    create_required_directories()
    create_db() # This already calls SQLModel.metadata.create_all
    initialize_database_and_admin_user() 
    print("Startup events completed.")

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