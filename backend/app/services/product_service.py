import json
from pathlib import Path
from typing import List, Optional
from ..models.product import Product


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "products.json"


class ProductService:
    _cache: List[Product] = []

    @classmethod
    def _load_products(cls) -> List[Product]:
        if cls._cache:
            return cls._cache

        try:
            with DATA_FILE.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except FileNotFoundError:
            payload = []

        cls._cache = [Product(**item) for item in payload]
        return cls._cache

    @classmethod
    def get_all_products(cls) -> List[Product]:
        return cls._load_products()

    @classmethod
    def get_product_by_id(cls, product_id: str) -> Optional[Product]:
        return next((p for p in cls._load_products() if p.id == product_id), None)
