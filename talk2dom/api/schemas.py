from pydantic import BaseModel
from typing import Optional, List


class LocatorRequest(BaseModel):
    url: str
    html: str
    user_instruction: str
    conversation_history: Optional[List[List[str]]] = None
    model: Optional[str] = "gpt-4o"
    model_provider: Optional[str] = "openai"


class LocatorResponse(BaseModel):
    selector_type: str
    selector_value: str
