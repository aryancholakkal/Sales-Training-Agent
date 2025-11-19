from typing import List, Optional
from pydantic import BaseModel


class Product(BaseModel):
	id: str
	name: str
	tagline: Optional[str] = None
	description: Optional[str] = None
	price: Optional[str] = None
	key_benefits: Optional[List[str]] = None
	usage_notes: Optional[str] = None


class ProductResponse(BaseModel):
	products: List[Product]
