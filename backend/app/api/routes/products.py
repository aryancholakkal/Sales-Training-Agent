from fastapi import APIRouter, HTTPException
from ...models.product import ProductResponse, Product
from ...services.product_service import ProductService

router = APIRouter()


@router.get("/", response_model=ProductResponse)
async def get_products():
    try:
        products = ProductService.get_all_products()
        return ProductResponse(products=products)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get products: {str(e)}")


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: str):
    product = ProductService.get_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product