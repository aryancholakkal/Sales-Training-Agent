from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from .session import TranscriptMessage


class EvaluationCategoryName(str, Enum):
	GRAMMAR_CLARITY = "Grammar & Clarity"
	TONE_EMPATHY = "Tone & Empathy"
	PRODUCT_KNOWLEDGE = "Product Knowledge"
	RESPONSE_STRATEGY = "Response Strategy"
	SALES_EFFECTIVENESS = "Sales Effectiveness"


class EvaluationCategoryFeedback(BaseModel):
	category: EvaluationCategoryName
	score: int = Field(ge=0, le=20)
	comment: str


class EvaluationRequest(BaseModel):
	persona_id: str
	product_id: Optional[str] = None
	transcript: List[TranscriptMessage] = Field(default_factory=list)
	conversation_summary: Optional[str] = None


class EvaluationResponse(BaseModel):
	report_id: str
	persona_id: str
	product_id: Optional[str] = None
	created_at: datetime
	overall_score: int = Field(ge=0, le=100)
	summary_feedback: str
	detailed_feedback: List[EvaluationCategoryFeedback]

	@property
	def category_average(self) -> float:
		if not self.detailed_feedback:
			return 0.0
		return sum(item.score for item in self.detailed_feedback) / len(self.detailed_feedback)
