import logging

from fastapi import APIRouter, HTTPException

from ...models.evaluation import EvaluationRequest, EvaluationResponse
from ...services.evaluation_service import EvaluationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", response_model=EvaluationResponse)
async def create_evaluation(payload: EvaluationRequest) -> EvaluationResponse:
    """Evaluate a completed conversation transcript."""
    try:
        return await EvaluationService.evaluate(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive safeguard
        logger.exception("Failed to evaluate conversation", exc_info=exc)
        raise HTTPException(status_code=500, detail="Failed to evaluate conversation") from exc
