from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class EvaluationResult:
    is_correct: bool
    score: int  # 0 to 100
    feedback: Dict[str, Any] = field(default_factory=dict)


class BaseStepEvaluator:
    def __init__(self, step_detail):
        self.step_detail = step_detail

    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        raise NotImplementedError("Subclasses must implement evaluate()")


class MultipleChoiceEvaluator(BaseStepEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        selected_choice_id = client_payload.get('selected_choice_id')
        if not selected_choice_id:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Missing selected_choice_id"})

        # N+1 Safe: Use the prefetched choices list if available
        # This avoids a DB query if the queryset used .prefetch_related('choices')
        choices = list(self.step_detail.choices.all())
        
        selected_choice = next((c for c in choices if str(c.id) == str(selected_choice_id)), None)
        
        if not selected_choice:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Invalid choice ID"})

        if selected_choice.is_correct:
            return EvaluationResult(is_correct=True, score=100)
        
        # Find the correct answer for feedback
        correct_choice = next((c for c in choices if c.is_correct), None)
        return EvaluationResult(
            is_correct=False, 
            score=0, 
            feedback={"correct_choice_id": correct_choice.id if correct_choice else None}
        )


class FillBlankEvaluator(BaseStepEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        user_answer = client_payload.get('text', '').strip().lower()
        if not user_answer:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Text is empty"})

        acceptable_answers = [ans.strip().lower() for ans in self.step_detail.acceptable_answers]

        if user_answer in acceptable_answers:
            return EvaluationResult(is_correct=True, score=100)
        
        return EvaluationResult(
            is_correct=False, 
            score=0, 
            feedback={"acceptable_answers": self.step_detail.acceptable_answers}
        )


class MatchPairsEvaluator(BaseStepEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        submitted_pairs = client_payload.get('pairs', [])  # list of {left_id, right_id}
        if not submitted_pairs:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "No pairs submitted"})

        actual_pairs = list(self.step_detail.pairs.all())
        if len(submitted_pairs) != len(actual_pairs):
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Incomplete mapping"})

        # Map actual pairs for easier lookup
        # We'll use IDs of the MatchPairItem rows to identify correctly
        correct_count = 0
        for pair in actual_pairs:
            # A correct match means the submitted payload has a pair that matches this actual pair row
            # Usually frontend sends some ID or text. Let's assume frontend sends MatchPairItem IDs for simplicity
            # or we can compare left/right identifiers.
            # Production approach: check if left_id maps to correct right_id
            # Let's assume payload: [{"left_id": item_id, "right_id": item_id}, ...]
            for sub in submitted_pairs:
                if str(sub.get('left_id')) == str(pair.id) and str(sub.get('right_id')) == str(pair.id):
                    correct_count += 1
                    break

        is_correct = correct_count == len(actual_pairs)
        score = 100 if is_correct else int((correct_count / len(actual_pairs)) * 100)
        
        return EvaluationResult(is_correct=is_correct, score=score)


class ReorderSentenceEvaluator(BaseStepEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        submitted_ids = client_payload.get('token_ids', [])  # list of ReorderToken IDs
        if not submitted_ids:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "No tokens submitted"})

        # N+1 Safe: Use Python filtering on prefetched list if available
        # Get non-distractor tokens in correct order
        all_tokens = list(self.step_detail.tokens.all())
        correct_tokens = sorted(
            [t for t in all_tokens if not t.is_distractor], 
            key=lambda t: t.sort_order
        )
        correct_ids = [str(t.id) for t in correct_tokens]
        submitted_ids_str = [str(tid) for tid in submitted_ids]

        if submitted_ids_str == correct_ids:
            return EvaluationResult(is_correct=True, score=100)
        
        return EvaluationResult(is_correct=False, score=0, feedback={"correct_order": correct_ids})


class TypeTranslationEvaluator(BaseStepEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        user_text = client_payload.get('text', '').strip().lower()
        if not user_text:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Text is empty"})

        acceptable = [a.strip().lower() for a in self.step_detail.acceptable_answers]

        if user_text in acceptable:
            return EvaluationResult(is_correct=True, score=100)
        
        return EvaluationResult(is_correct=False, score=0, feedback={"acceptable_answers": self.step_detail.acceptable_answers})


class SpeakPhraseEvaluator(BaseStepEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        # For speaking, the score is calculated by an async provider
        # The evaluator is used after scoring to determine correctness
        score = client_payload.get('score', 0)
        is_correct = score >= self.step_detail.min_score_required
        
        return EvaluationResult(
            is_correct=is_correct,
            score=score,
            feedback=client_payload.get('feedback', {})
        )
