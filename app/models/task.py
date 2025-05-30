from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TaskStatus(BaseModel):
    task_id: str
    status: str  # "pending", "processing", "completed", "failed"
    files: Optional[List[str]] = None
    error: Optional[str] = None
    created_at: datetime = datetime.now()
    expires_at: Optional[datetime] = None 