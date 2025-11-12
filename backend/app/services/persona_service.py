import json
from typing import List, Optional
from ..models.persona import Persona
from ..core.config import get_settings
from ..models.product import Product

class PersonaService:
    @staticmethod
    def get_all_personas(product: Product | None = None) -> List[Persona]:
        """Get all available personas"""
        settings = get_settings()
        personas_data = json.loads(settings.personas_json)
        product_name = product.name if product else settings.product_name
        return [
            Persona(
                id=persona["id"],
                name=persona["name"],
                description=persona["description"],
                avatar=persona["avatar"],
                system_instruction=persona["system_instruction"].format(product_name=product_name)
            )
            for persona in personas_data
        ]
    
    @staticmethod
    def get_persona_by_id(persona_id: str, product: Product | None = None) -> Optional[Persona]:
        """Get a specific persona by ID"""
        personas = PersonaService.get_all_personas(product=product)
        return next((p for p in personas if p.id == persona_id), None)
    



# Top-level function for prompt composition
from app.core.config import SYSTEM_PROMPT


def _format_product_context(product: Product | None) -> str:
    if not product:
        return ""

    details = [f"Product Name: {product.name}"]
    if product.tagline:
        details.append(f"Tagline: {product.tagline}")
    if product.description:
        details.append(f"Description: {product.description}")
    if product.price:
        details.append(f"Price: {product.price}")
    if product.key_benefits:
        benefits = "\n- ".join(product.key_benefits)
        details.append(f"Key Benefits:\n- {benefits}")
    if product.usage_notes:
        details.append(f"Usage Notes: {product.usage_notes}")

    return "\n\n" + "\n".join(details)


def get_persona_prompt(persona, product: Product | None = None):
    """
    Returns the combined system prompt for the selected persona.
    """
    # Prepend global system prompt to persona instruction
    product_context = _format_product_context(product)
    return f"{SYSTEM_PROMPT}\n\n{persona.system_instruction}{product_context}"