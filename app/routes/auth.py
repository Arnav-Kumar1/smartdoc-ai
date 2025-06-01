from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlmodel import Session, select
from datetime import timedelta
from app.models.user import User, UserCreate, UserResponse, UserLogin
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

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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
def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists - case insensitive email check
    normalized_email = user.email.lower()
    existing_user = db.exec(select(User).where(User.email.ilike(f"{normalized_email}"))).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user with normalized email
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=normalized_email,  # Store email in lowercase
        username=user.username,
        hashed_password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        username=db_user.username,
        created_at=db_user.created_at
    )

@router.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Case insensitive email lookup
    normalized_email = form_data.username.lower()
    user = db.exec(select(User).where(User.email.ilike(f"{normalized_email}"))).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please sign up first.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
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
def read_users_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        created_at=current_user.created_at
    )

@router.get("/test-db")
async def test_db(db: Session = Depends(get_db)):
    try:
        users = db.query(User).all()
        return {"message": "Database connection successful", "user_count": len(users)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    print(f"Attempting to register user: {user.email}")  # Debug log
    
    # Check if user exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        print(f"User already exists: {user.email}")  # Debug log
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        print(f"User registered successfully: {user.email}")  # Debug log
        return db_user
    except Exception as e:
        print(f"Error registering user: {str(e)}")  # Debug log
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/debug/db")
async def debug_db(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {
        "user_count": len(users),
        "database_path": db.get_bind().engine.url.database
    }