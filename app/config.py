import os
from dotenv import load_dotenv

def load_env_vars():
    load_dotenv()

# Define base directories
# Change from app/data to root data directory

TOP_K_CHUNKS = 20  # You can tweak this later

# Base data directory at project root
BASE_DATA_DIR = os.path.join(os.getcwd(), 'data')

# Subdirectories under data
UPLOAD_DIR = os.path.join(BASE_DATA_DIR, 'uploaded_files')
VECTOR_STORE_DIR = os.path.join(BASE_DATA_DIR, 'vector_store')
DB_DIR = os.path.join(BASE_DATA_DIR, 'Database') # this code will make a folder called 'Database' in the data folder

# Create all required directories
def create_required_directories():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
    os.makedirs(DB_DIR, exist_ok=True)

