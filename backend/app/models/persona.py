from pydantic import BaseModel
from typing import List


class Persona(BaseModel):
    id: str
    name: str
    description: str
    avatar: str
    system_instruction: str


class PersonaResponse(BaseModel):
    personas: List[Persona]