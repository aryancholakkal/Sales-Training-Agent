from fastapi import APIRouter, HTTPException
from typing import List
from ...models.persona import Persona, PersonaResponse
from ...services.persona_service import PersonaService

router = APIRouter()


@router.get("/", response_model=PersonaResponse)
async def get_personas():
    """Get all available personas"""
    try:
        personas = PersonaService.get_all_personas()
        return PersonaResponse(personas=personas)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get personas: {str(e)}")


@router.get("/{persona_id}", response_model=Persona)
async def get_persona(persona_id: str):
    """Get a specific persona by ID"""
    try:
        persona = PersonaService.get_persona_by_id(persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return persona
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get persona: {str(e)}")