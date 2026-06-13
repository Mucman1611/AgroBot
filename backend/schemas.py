from pydantic import BaseModel
from typing import Optional

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    role: str = "farmer"
    delegated_to_id: Optional[int] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class FarmCreate(BaseModel):
    name: str
    location: str
    total_area_ha: float

class AgentFarmCreate(BaseModel):
    name: str
    location: str
    total_area_ha: float
    owner_email: str

class ApplicationSubmit(BaseModel):
    competition_id: int
    notes: Optional[str] = None