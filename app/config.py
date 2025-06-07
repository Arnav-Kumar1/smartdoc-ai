import os
from dotenv import load_dotenv

def load_env_vars():
    load_dotenv()

# Define base directories
# Change from app/data to root data directory


# Lock to specific embedding model
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

# Base data directory at project root
BASE_DATA_DIR = os.path.join(os.getcwd(), 'data')

# Subdirectories under data
UPLOAD_DIR = os.path.join(BASE_DATA_DIR, 'uploaded_files')
VECTOR_STORE_DIR = os.path.join(BASE_DATA_DIR, 'vector_store')
DB_DIR = os.path.join(BASE_DATA_DIR, 'db')

# Create all required directories
def create_required_directories():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
    os.makedirs(DB_DIR, exist_ok=True)

