from sqlmodel import create_engine, Session, SQLModel
import os
from app.config import DB_DIR
# Ensure app/data/db directory exists
# Change from app/data/db to data/db

SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(DB_DIR, 'database.db')}"

# Connect to the database with additional parameters
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
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
