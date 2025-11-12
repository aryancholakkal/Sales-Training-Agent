from fastapi import APIRouter, HTTPException, Query
from typing import List
from ...models.persona import Persona, PersonaResponse
from ...services.persona_service import PersonaService
from ...services.product_service import ProductService

router = APIRouter()


@router.get("/", response_model=PersonaResponse)
async def get_personas(product_id: str | None = Query(default=None)):
    """Get all available personas"""
    try:
        product = ProductService.get_product_by_id(product_id) if product_id else None
        personas = PersonaService.get_all_personas(product=product)
        return PersonaResponse(personas=personas)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get personas: {str(e)}")


@router.get("/{persona_id}", response_model=Persona)
async def get_persona(persona_id: str, product_id: str | None = Query(default=None)):
    """Get a specific persona by ID"""
    try:
        product = ProductService.get_product_by_id(product_id) if product_id else None
        persona = PersonaService.get_persona_by_id(persona_id, product=product)
        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")
        return persona
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get persona: {str(e)}")