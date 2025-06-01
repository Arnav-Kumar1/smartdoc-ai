from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "55ee5456661a1ab712a2127c51528800f02d356d9455c59952c341f58cb8164c")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def authenticated_request(method, endpoint, json=None, headers=None):
    """
    Make authenticated API request with JWT from environment
    Returns response object or None if failed
    """
    token = os.getenv("JWT_TOKEN")
    if not token:
        print("No JWT token found in environment")
        return None

    headers = headers or {}
    headers.update({"Authorization": f"Bearer {token}"})

    try:
        response = method(
            f"http://localhost:8000{endpoint}",
            json=json,
            headers=headers
        )
        response.raise_for_status()
        return response
    except Exception as e:
        print(f"API request failed: {str(e)}")
        return None