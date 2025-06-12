# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import time
from passlib.context import CryptContext
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

# --- Password Hashing Context ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hashes a plaintext password."""
    return pwd_context.hash(password)

# --- Function to initialize database and admin user (Moved from main_utils.py) ---
def initialize_database_and_admin_user():
    print("Attempting to initialize database and admin user...")

    # Sleep briefly to ensure file system mounts are stable (optional, but can help)
    time.sleep(5) 

    # Construct the full path to your SQLite database file
    db_file_name = "database.db" # <--- Corrected database file name to match app/database.py
    db_full_path = os.path.join(DB_DIR, db_file_name)
    
    # Ensure the database directory exists (redundant if create_required_directories runs first, but safe)
    os.makedirs(DB_DIR, exist_ok=True)
    print(f"Ensured database directory '{DB_DIR}' exists.")

    db_file_exists = os.path.exists(db_full_path)

    if not db_file_exists:
        print(f"Database file '{db_full_path}' not found. Creating schema.")
        try:
            # Corrected: Use SQLModel.metadata.create_all as per your database.py
            SQLModel.metadata.create_all(bind=engine) 
            print("Database tables created successfully.")
        except Exception as e:
            print(f"Error creating database tables: {e}")
            raise

    # Corrected: Use Session(engine) to get a session
    with Session(engine) as db: 
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_raw_password = os.getenv("ADMIN_PASSWORD")

        if not admin_email or not admin_raw_password:
            print("WARNING: ADMIN_EMAIL or ADMIN_PASSWORD environment variables not set. Skipping admin user initialization.")
            print("Please ensure these are set in your .env file or deployment environment.")
            return

        print(f"Checking for admin user with email: {admin_email}")
        existing_admin = db.query(User).filter(User.email == admin_email).first()

        if not existing_admin:
            print(f"Admin user '{admin_email}' not found. Creating new admin user.")
            hashed_password = get_password_hash(admin_raw_password)
            new_admin = User(
                username="Initial Admin",
                email=admin_email,
                hashed_password=hashed_password,
                is_admin=True,
                is_active=True,
                # 'created_at' is handled by its default_factory in the User model, no need to set here
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
            
            if not pwd_context.verify(admin_raw_password, existing_admin.hashed_password):
                 print(f"Updating password for admin user '{admin_email}'.")
                 existing_admin.hashed_password = get_password_hash(admin_raw_password)
            
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