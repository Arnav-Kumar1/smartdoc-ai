from sqlmodel import create_engine, Session, SQLModel
from .models.document import Document
import os

# Ensure app/data/db directory exists
DB_DIR = os.path.join("app", "data", "db")
os.makedirs(DB_DIR, exist_ok=True)

# SQLite database URL - Using absolute path
DB_PATH = os.path.join(os.path.abspath(DB_DIR), "smartdoc_ai.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Connect to the database with additional parameters
engine = create_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False}
)

# Create database tables
def create_db():
    SQLModel.metadata.create_all(bind=engine)

# Get database session
def get_db():
    with Session(engine) as session:
        yield session  # FastAPI will automatically handle the session lifecycle
