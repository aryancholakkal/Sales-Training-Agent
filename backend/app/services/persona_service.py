import json
from typing import List, Optional
from ..models.persona import Persona
from ..core.config import get_settings

class PersonaService:
    @staticmethod
    def get_all_personas() -> List[Persona]:
        """Get all available personas"""
        settings = get_settings()
        personas_data = json.loads(settings.personas_json)
        return [
            Persona(
                id=persona["id"],
                name=persona["name"],
                description=persona["description"],
                avatar=persona["avatar"],
                system_instruction=persona["system_instruction"].format(product_name=settings.product_name)
            )
            for persona in personas_data
        ]
    
    @staticmethod
    def get_persona_by_id(persona_id: str) -> Optional[Persona]:
        """Get a specific persona by ID"""
        personas = PersonaService.get_all_personas()
        return next((p for p in personas if p.id == persona_id), None)