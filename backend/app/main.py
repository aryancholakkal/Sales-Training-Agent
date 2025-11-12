import logging
import os
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api.routes import personas, websocket, products, evaluations

# Configure logging
# Ensure logs directory exists under backend/logs
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_DIR = os.path.normpath(LOG_DIR)
os.makedirs(LOG_DIR, exist_ok=True)

# Create a root logger with timestamped format and a rotating file handler
log_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Console handler (keeps previous behavior)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
root_logger.addHandler(console_handler)

# File handler with rotation
log_file_path = os.path.join(LOG_DIR, "app.log")
file_handler = RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
file_handler.setFormatter(log_formatter)
root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    debug=settings.debug
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(personas.router, prefix="/api/personas", tags=["personas"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])
app.include_router(evaluations.router, prefix="/api/evaluations", tags=["evaluations"])


@app.get("/")
async def root():
    return {"message": "AI Sales Training Backend", "version": settings.version}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )