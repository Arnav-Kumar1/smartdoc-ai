# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import time
from datetime import datetime # Added for datetime.utcnow() (though default_factory handles creation time)
# --- Database Imports ---
from app.database import create_db, engine # engine is needed for session and metadata.create_all
from sqlmodel import Session, SQLModel, select # Session and SQLModel.metadata are used

# --- Import password hashing/verification functions ---
from app.auth.auth_utils import get_password_hash, verify_password # <-- ADD THIS LINE

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

    # Optional, but can help with file system stability on some systems/deployments
    time.sleep(5) 

    # --- Get admin user details from environment variables ---
    admin_email = os.getenv("ADMIN_EMAIL")
    print("admin_email:", admin_email)

    admin_raw_password = os.getenv("ADMIN_PASSWORD")
    print("admin raw password",admin_raw_password)

    admin_username = os.getenv("ADMIN_USERNAME")
    print("Admin Username", admin_username)

    # This line attempts to get the GOOGLE_API_KEY from environment variables
    admin_gemini_api_key = os.getenv("GOOGLE_API_KEY") 
    print("Admin Gemini API Key:", admin_gemini_api_key) # Changed variable name for consistency in function

    # Corrected the warning message to reflect the actual variable being checked
    if not admin_email or not admin_raw_password or not admin_username or not admin_gemini_api_key:
        print("WARNING: Admin user environment variables (ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_USERNAME, GOOGLE_API_KEY) are not fully set.")
        print("Admin user initialization skipped. Please set them to create an admin user.")
        return

    # Normalize email to lowercase
    admin_email = admin_email.lower()

    with Session(engine) as db:
        existing_admin = db.exec(select(User).where(User.email == admin_email)).first()

        if not existing_admin:
            # Admin user does not exist, create a new one
            print(f"Admin user '{admin_email}' not found. Creating a new admin user...")
            
            # Hash the admin password using the imported function
            hashed_password = get_password_hash(admin_raw_password)

            new_admin = User(
                email=admin_email,
                username=admin_username,
                hashed_password=hashed_password,
                is_admin=True, # Grant admin privileges to the initial user
                gemini_api_key=admin_gemini_api_key, # Use the correctly read variable
                created_at=datetime.utcnow() # Set creation timestamp
            )
            db.add(new_admin)
            db.commit()
            db.refresh(new_admin)
            print(f"New admin user '{admin_email}' created successfully with admin privileges.")
        else: # Admin user already exists
            print(f"Admin user '{admin_email}' already exists. Ensuring admin privileges and password.")
            needs_update = False

            # Check if admin privileges need to be granted
            if not existing_admin.is_admin:
                print(f"Granting admin privileges to '{admin_email}'.")
                existing_admin.is_admin = True
                needs_update = True
                print(f"User '{admin_email}' granted admin privileges.") # Print after setting True

            # Check if password needs to be updated using the imported verify_password
            if not verify_password(admin_raw_password, existing_admin.hashed_password):
                print(f"Updating password for admin user '{admin_email}'.")
                existing_admin.hashed_password = get_password_hash(admin_raw_password)
                needs_update = True # Mark for update

            # Ensure Gemini API key is set for existing admin as well
            if existing_admin.gemini_api_key != admin_gemini_api_key: # Compare with correctly read variable
                print(f"Updating Gemini API key for admin user '{admin_email}'.")
                existing_admin.gemini_api_key = admin_gemini_api_key # Use the correctly read variable
                needs_update = True

            # Only commit and refresh if any changes were made
            if needs_update:
                db.commit()
                db.refresh(existing_admin)
                print(f"Admin user '{admin_email}' state updated.")
            else:
                print(f"Admin user '{admin_email}' is already up to date. No changes applied.")

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