from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import Column, DateTime
from datetime import timezone

class Document(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    filename: str
    file_type: str
    upload_time: datetime = Field(
        sa_column=Column(DateTime(timezone=True))
    )
    path: str
    summary: Optional[str] = None
    is_vectorized: bool = Field(default=False)  # Track vectorization status
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    file_hash: Optional[str] = None  # Store file hash to identify identical files


from pydantic import BaseModel
from typing import List

class BatchDeleteRequest(BaseModel):
    document_ids: List[str]
