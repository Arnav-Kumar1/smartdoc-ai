# debug_hash.py
import os
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv() # Load your .env if you use one locally, otherwise remove this line.

# Ensure this context matches what's in app/auth/auth_utils.py
# It should be pbkdf2_sha256, not bcrypt
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# PASTE THE PASSWORD HERE - VERY CAREFULLY!
# Replace 'PASTE_RAILWAY_ADMIN_PASSWORD_HERE' with the exact value copied from Railway.
# Ensure there are no extra spaces or newlines if you copy-pasted.
# Consider typing it out manually if copying is problematic.
admin_password_from_railway_env = "a"

generated_hash = get_password_hash(admin_password_from_railway_env)

print(f"Plaintext Password (from Railway ENV): '{admin_password_from_railway_env}'")
print(f"Generated Hash for this password: {generated_hash}")