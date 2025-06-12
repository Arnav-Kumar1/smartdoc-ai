from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from datetime import timedelta
from app.models.user import User, UserCreate, UserResponse
from app.auth.auth_utils import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    decode_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from app.database import get_db
from uuid import UUID
from typing import Optional
import google.generativeai as genai
import os 
import asyncio # NEW: Import asyncio for timeout handling

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def validate_gemini_api_key(api_key: str, timeout: int = 10) -> bool:
    """
    Attempts a simple Gemini API call to validate the provided API key with a timeout.
    Runs the blocking genai call in a separate thread to prevent FastAPI from hanging.
    """
    print(f"--- Starting async API key validation for key (first 5 chars): {api_key[:5]}...")

    if not api_key or api_key.strip() == "":
        print("Validation failed: API key is empty or whitespace.")
        return False
    
    original_google_api_key_env = os.environ.get("GOOGLE_API_KEY")
    if original_google_api_key_env:
        del os.environ["GOOGLE_API_KEY"]

    def _perform_validation_sync():
        """Synchronous part of the validation to be run in a thread."""
        try:
            genai.configure(api_key=api_key)
            models = genai.list_models()

            for model in models:
                if "generateContent" in model.supported_generation_methods:
                    print(f"  _perform_validation_sync: Found usable model '{model.name}'. Key seems valid.")
                    return True
            print("  _perform_validation_sync: API key accepted, but no usable 'generateContent' models found.")
            return False

        except GoogleAPIError as e:
            print(f"  _perform_validation_sync: Gemini API key validation failed (GoogleAPIError): {e}")
            return False
        except Exception as e:
            print(f"  _perform_validation_sync: Gemini API key validation failed (Unexpected Error): {type(e).__name__}: {e}")
            return False
        finally:
            if original_google_api_key_env:
                os.environ["GOOGLE_API_KEY"] = original_google_api_key_env
                print("  _perform_validation_sync: Restored GOOGLE_API_KEY environment variable.")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_perform_validation_sync),
            timeout=timeout
        )
        print(f"--- Async API key validation result: {result}")
        return result
    except asyncio.TimeoutError:
        print(f"--- Gemini API key validation timed out after {timeout} seconds.")
        return False
    except Exception as e:
        print(f"--- An unexpected error occurred during API key validation (async wrapper): {type(e).__name__}: {e}")
        return False



async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Dependency to get the current authenticated user from the JWT token.
    Ensures the full User object, including the gemini_api_key, is returned.
    """
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = db.get(User, UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

@router.post("/signup", response_model=UserResponse)


async def signup(user: UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new user, validates their provided Gemini API key,
    and stores the key directly in the database.
    """
    print(f"Attempting to register user: {user.email}")
    
    # Check if user exists - case insensitive email check
    normalized_email = user.email.lower()
    existing_user = db.exec(select(User).where(User.email.ilike(f"{normalized_email}"))).first()
    if existing_user:
        print(f"User already exists: {user.email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # IMPORTANT FIX: Ensure API key is validated BEFORE creating the user
    # This prevents storing invalid keys and allowing signup with them.
    if not user.gemini_api_key or user.gemini_api_key.strip() == "":
        print("invalid")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gemini API Key cannot be empty.")

    # MODIFIED: Await the async validation function
    if not await validate_gemini_api_key(user.gemini_api_key):
        print("invalid")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Gemini API Key provided. Please check your key.")

    # Create new user with normalized email
    hashed_password = get_password_hash(user.password)

    db_user = User(
        email=normalized_email,
        username=user.username,
        hashed_password=hashed_password,
        gemini_api_key=user.gemini_api_key # Store the Gemini API key directly
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        print(f"User registered successfully: {user.email}")
        return UserResponse(
            id=db_user.id,
            email=db_user.email,
            username=db_user.username,
            created_at=db_user.created_at,
            is_active=db_user.is_active,
            is_admin=db_user.is_admin
        )
    except Exception as e:
        print(f"Error registering user: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Registration failed: {str(e)}")

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Authenticates user and generates an access token.
    Includes validation of the user's stored Gemini API key to prevent login with invalid keys.
    """
    # Case insensitive email lookup
    normalized_email = form_data.username.lower()

    # --- ADD THESE DEBUG PRINTS HERE ---
    print(f"DEBUG AUTH: Login attempt for email: '{normalized_email}'")
    # WARNING: Do NOT log raw passwords in production environments! This is for debugging only.
    print(f"DEBUG AUTH: Frontend provided password (raw): '{form_data.password}'")
    # --- END DEBUG PRINTS ---

    user = db.exec(select(User).where(User.email.ilike(f"{normalized_email}"))).first()

    if not user:
        print(f"DEBUG AUTH: User '{normalized_email}' NOT FOUND in database.") # Added debug print
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # --- ADD THESE DEBUG PRINTS HERE ---
    print(f"DEBUG AUTH: User '{user.email}' FOUND in database. Hashed password: '{user.hashed_password}'")
    # --- END DEBUG PRINTS ---

    if not verify_password(form_data.password, user.hashed_password):
        print(f"DEBUG AUTH: Password verification FAILED for user '{user.email}'.") # Added debug print
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"DEBUG AUTH: Password verification SUCCESS for user '{user.email}'.") # Added debug print

    # IMPORTANT FIX: Validate the user's stored Gemini API Key upon successful password verification
    if not user.gemini_api_key or user.gemini_api_key.strip() == "":
        print(f"DEBUG AUTH: Gemini API key missing for user '{user.email}'.") # Added debug print
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your Gemini API key is missing. Please update your profile or contact support.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # MODIFIED: Await the async validation function
    if not await validate_gemini_api_key(user.gemini_api_key):
        print(f"DEBUG AUTH: Gemini API key validation FAILED for user '{user.email}'.") # Added debug print
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your Gemini API key is invalid. Please update your key or contact support.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    print(f"DEBUG AUTH: Gemini API key validation SUCCESS for user '{user.email}'.") # Added debug print


    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": str(user.id),
        "username": user.username,
        "email": user.email
    }

@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        created_at=current_user.created_at,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin
    )

@router.get("/test-db")
async def test_db(db: Session = Depends(get_db)):
    try:
        users = db.query(User).all()
        return {"message": "Database connection successful", "user_count": len(users)}
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/db")
async def debug_db(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {
        "user_count": len(users),
        "database_path": db.get_bind().engine.url.database
    }
