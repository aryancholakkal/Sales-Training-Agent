from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from ..models.evaluation import (
	EvaluationCategoryFeedback,
	EvaluationCategoryName,
	EvaluationRequest,
	EvaluationResponse,
)
from ..models.session import TranscriptMessage
from ..services.product_service import ProductService

logger = logging.getLogger(__name__)


class EvaluationService:
	"""Rule-based evaluation pipeline that scores a finished conversation."""

	FILLER_WORDS = {"um", "uh", "like", "you know", "sort of", "kinda"}
	POSITIVE_WORDS = {
		"great",
		"awesome",
		"happy",
		"glad",
		"absolutely",
		"certainly",
		"definitely",
		"appreciate",
		"thank",
		"understand",
		"pleasure",
	}
	NEGATIVE_WORDS = {"can't", "cannot", "won't", "unfortunately", "hate", "terrible"}
	EMPATHY_PHRASES = {
		"i understand",
		"i totally get",
		"sorry to hear",
		"i hear you",
		"that makes sense",
		"i appreciate",
	}
	OBJECTION_PHRASES = {
		"what concerns",
		"how does that sound",
		"does that address",
		"let's explore",
		"help you with",
		"could you share",
	}
	VALUE_PHRASES = {
		"benefit",
		"value",
		"impact",
		"results",
		"improve",
		"increase",
		"reduce",
	}
	CLOSING_PHRASES = {
		"get started",
		"place the order",
		"sign up",
		"set you up",
		"next step",
		"schedule a follow",
		"move forward",
		"ready to",
		"would you like to",
	}
	CATEGORY_SEQUENCE = [
		EvaluationCategoryName.GRAMMAR_CLARITY,
		EvaluationCategoryName.TONE_EMPATHY,
		EvaluationCategoryName.PRODUCT_KNOWLEDGE,
		EvaluationCategoryName.RESPONSE_STRATEGY,
		EvaluationCategoryName.SALES_EFFECTIVENESS,
	]

	@classmethod
	async def evaluate(cls, request: EvaluationRequest) -> EvaluationResponse:
		messages = cls._prepare_transcript(request.transcript)
		if not messages:
			raise ValueError("Conversation transcript is empty.")

		trainee_texts = [msg.text for msg in messages if msg.speaker == "Trainee" and msg.text.strip()]
		if not trainee_texts:
			raise ValueError("Transcript does not contain trainee messages to evaluate.")

		product = ProductService.get_product_by_id(request.product_id) if request.product_id else None

		trainee_blob = " ".join(trainee_texts)
		trainee_words = cls._tokenize(trainee_blob)

		scores: Dict[EvaluationCategoryName, int] = {}
		comments: Dict[EvaluationCategoryName, str] = {}

		scores[EvaluationCategoryName.GRAMMAR_CLARITY] = cls._score_grammar_and_clarity(trainee_texts, trainee_words)
		comments[EvaluationCategoryName.GRAMMAR_CLARITY] = cls._commentary(
			EvaluationCategoryName.GRAMMAR_CLARITY,
			scores[EvaluationCategoryName.GRAMMAR_CLARITY],
		)

		scores[EvaluationCategoryName.TONE_EMPATHY] = cls._score_tone_and_empathy(trainee_blob, trainee_words)
		comments[EvaluationCategoryName.TONE_EMPATHY] = cls._commentary(
			EvaluationCategoryName.TONE_EMPATHY,
			scores[EvaluationCategoryName.TONE_EMPATHY],
		)

		scores[EvaluationCategoryName.PRODUCT_KNOWLEDGE] = cls._score_product_knowledge(trainee_blob, trainee_words, product)
		comments[EvaluationCategoryName.PRODUCT_KNOWLEDGE] = cls._commentary(
			EvaluationCategoryName.PRODUCT_KNOWLEDGE,
			scores[EvaluationCategoryName.PRODUCT_KNOWLEDGE],
		)

		scores[EvaluationCategoryName.RESPONSE_STRATEGY] = cls._score_response_strategy(trainee_texts, trainee_blob)
		comments[EvaluationCategoryName.RESPONSE_STRATEGY] = cls._commentary(
			EvaluationCategoryName.RESPONSE_STRATEGY,
			scores[EvaluationCategoryName.RESPONSE_STRATEGY],
		)

		scores[EvaluationCategoryName.SALES_EFFECTIVENESS] = cls._score_sales_effectiveness(trainee_blob)
		comments[EvaluationCategoryName.SALES_EFFECTIVENESS] = cls._commentary(
			EvaluationCategoryName.SALES_EFFECTIVENESS,
			scores[EvaluationCategoryName.SALES_EFFECTIVENESS],
		)

		detailed_feedback = [
			EvaluationCategoryFeedback(category=category, score=score, comment=comments[category])
			for category, score in scores.items()
		]
		order_lookup = {category: index for index, category in enumerate(cls.CATEGORY_SEQUENCE)}
		detailed_feedback.sort(key=lambda item: order_lookup.get(item.category, len(cls.CATEGORY_SEQUENCE)))

		overall_score = sum(item.score for item in detailed_feedback)
		summary = cls._build_summary(detailed_feedback)

		logger.info(
			"Generated evaluation report",
			extra={
				"persona_id": request.persona_id,
				"product_id": request.product_id,
				"overall_score": overall_score,
			},
		)

		return EvaluationResponse(
			report_id=str(uuid4()),
			persona_id=request.persona_id,
			product_id=request.product_id,
			created_at=datetime.now(timezone.utc),
			overall_score=overall_score,
			summary_feedback=summary,
			detailed_feedback=detailed_feedback,
		)

	@classmethod
	def _prepare_transcript(cls, transcript: Iterable[TranscriptMessage]) -> List[TranscriptMessage]:
		messages: List[TranscriptMessage] = []
		seen_ids: set[int] = set()
		for index, message in enumerate(transcript):
			if message.is_final is False:
				continue
			if not message.text or not message.text.strip():
				continue
			message_id = message.id if message.id is not None else index
			if message_id in seen_ids:
				continue
			seen_ids.add(message_id)
			messages.append(message)
		return messages

	@staticmethod
	def _tokenize(text: str) -> List[str]:
		if not text:
			return []
		return re.findall(r"[a-zA-Z']+", text.lower())

	@classmethod
	def _score_grammar_and_clarity(cls, trainee_texts: List[str], trainee_words: List[str]) -> int:
		if not trainee_texts:
			return 10

		sentences: List[str] = []
		for text in trainee_texts:
			sentences.extend([segment.strip() for segment in re.split(r"[.!?]+", text) if segment.strip()])

		sentence_count = max(1, len(sentences))
		word_count = len(trainee_words)
		avg_sentence_length = word_count / sentence_count if sentence_count else 0

		punctuated = sum(1 for text in trainee_texts if text.strip().endswith((".", "!", "?")))
		punctuation_ratio = punctuated / max(1, len(trainee_texts))

		filler_hits = sum(1 for word in trainee_words if word in cls.FILLER_WORDS)
		filler_ratio = filler_hits / max(1, word_count)

		clarity_component = max(0.0, 1.0 - min(1.0, abs(avg_sentence_length - 14) / 14))
		punctuation_component = min(1.0, punctuation_ratio)
		filler_penalty = min(0.6, filler_ratio * 4)

		raw_score = 0.55 * clarity_component + 0.35 * punctuation_component - filler_penalty
		normalized = max(0.0, min(1.0, 0.5 + raw_score))
		return cls._to_twenty_scale(normalized)

	@classmethod
	def _score_tone_and_empathy(cls, trainee_blob: str, trainee_words: List[str]) -> int:
		if not trainee_blob:
			return 10

		word_counter = Counter(trainee_words)
		positive_hits = sum(word_counter[word] for word in cls.POSITIVE_WORDS)
		negative_hits = sum(word_counter[word] for word in cls.NEGATIVE_WORDS)
		empathy_hits = sum(1 for phrase in cls.EMPATHY_PHRASES if phrase in trainee_blob.lower())

		sentiment = positive_hits + 2 * empathy_hits - 2 * negative_hits
		normalized = max(0.0, min(1.0, (sentiment + 5) / 10))
		return cls._to_twenty_scale(normalized)

	@classmethod
	def _score_product_knowledge(
		cls,
		trainee_blob: str,
		trainee_words: List[str],
		product: Optional[object],
	) -> int:
		if not trainee_blob:
			return 8

		keywords: set[str] = set()
		if product:
			keywords.update(cls._tokenize(product.name))
			if getattr(product, "tagline", None):
				keywords.update(cls._tokenize(product.tagline))
			if getattr(product, "description", None):
				keywords.update(cls._tokenize(product.description))
			benefits = getattr(product, "key_benefits", None)
			if benefits:
				for benefit in benefits:
					keywords.update(cls._tokenize(benefit))

		if not keywords:
			keywords = {"feature", "benefit", "ingredient", "price", "package", "guarantee"}

		word_set = set(trainee_words)
		matched_keywords = sum(1 for keyword in keywords if keyword in word_set)
		depth_mentions = sum(1 for phrase in cls.VALUE_PHRASES if phrase in trainee_blob.lower())

		coverage = min(1.0, matched_keywords / max(3, len(keywords)))
		depth_component = min(1.0, depth_mentions / 4)
		normalized = 0.6 * coverage + 0.4 * depth_component
		return cls._to_twenty_scale(normalized)

	@classmethod
	def _score_response_strategy(cls, trainee_texts: List[str], trainee_blob: str) -> int:
		if not trainee_texts:
			return 10

		question_count = sum(text.count("?") for text in trainee_texts)
		objection_handling = sum(1 for phrase in cls.OBJECTION_PHRASES if phrase in trainee_blob.lower())

		normalized = min(1.0, (question_count + 2 * objection_handling) / 8)
		return cls._to_twenty_scale(normalized)

	@classmethod
	def _score_sales_effectiveness(cls, trainee_blob: str) -> int:
		if not trainee_blob:
			return 9

		text_lower = trainee_blob.lower()
		closing_hits = sum(1 for phrase in cls.CLOSING_PHRASES if phrase in text_lower)
		value_hits = sum(1 for phrase in cls.VALUE_PHRASES if phrase in text_lower)

		normalized = min(1.0, (2 * closing_hits + value_hits) / 8)
		return cls._to_twenty_scale(normalized)

	@staticmethod
	def _commentary(category: EvaluationCategoryName, score: int) -> str:
		if score >= 17:
			tone = "Outstanding"
			guidance = "Keep pushing this strength into every pitch."
		elif score >= 13:
			tone = "Solid"
			guidance = "Look for small refinements to move into excellence."
		elif score >= 9:
			tone = "Developing"
			guidance = "Focus here during your next practice session."
		else:
			tone = "Needs Attention"
			guidance = "Review the fundamentals and rehearse targeted drills."

		return f"{tone} {category.value}. {guidance}"

	@staticmethod
	def _to_twenty_scale(value: float) -> int:
		clamped = max(0.0, min(1.0, value))
		return int(round(clamped * 20))

	@staticmethod
	def _build_summary(feedback: List[EvaluationCategoryFeedback]) -> str:
		if not feedback:
			return "No feedback available."

		sorted_feedback = sorted(feedback, key=lambda item: item.score, reverse=True)
		strengths = sorted_feedback[0]
		opportunities = sorted_feedback[-1]

		if strengths.category == opportunities.category:
			return (
				"Your performance was balanced across the evaluated skills. Maintain your current habits and "
				"continue practicing targeted scenarios to lift your overall score."
			)

		return (
			f"You excelled at {strengths.category.value.lower()} with a {strengths.score}/20. "
			f"Prioritize improving {opportunities.category.value.lower()} to lift your next conversation."
		)

