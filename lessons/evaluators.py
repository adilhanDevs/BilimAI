import re
import string
import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from .utils.text_utils import normalize_text, resolve_answer_text, group_answers_by_blank
from .utils.cache import get_cached_translation

logger = logging.getLogger(__name__)

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
        selected_id = client_payload.get('selected_choice_id')
        selected_ids = client_payload.get('selected_choice_ids', [])
        
        # Consolidate into a set of strings for easier comparison
        submitted_ids = set()
        if selected_id:
            submitted_ids.add(str(selected_id))
        for sid in selected_ids:
            submitted_ids.add(str(sid))

        if not submitted_ids:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "No choice selected"})

        # N+1 Safe: Use the prefetched choices list if available
        choices = list(self.step_detail.choices.all())
        correct_choices = [c for c in choices if c.is_correct]
        correct_ids = {str(c.id) for c in correct_choices}
        
        # User must select EXACTLY all correct answers (and only them)
        is_correct = submitted_ids == correct_ids

        if is_correct:
            return EvaluationResult(is_correct=True, score=100)
        
        return EvaluationResult(
            is_correct=False, 
            score=0, 
            feedback={"correct_choice_ids": list(correct_ids)}
        )


class FillBlankEvaluator(BaseStepEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        lang = client_payload.get('lang', 'en')
        user_answers = client_payload.get('answers', [])
        
        # Primary path: Relational StepAnswer objects
        rel_answers = list(getattr(self.step_detail, 'relational_answers', self.step_detail.relational_answers.none()).all())
        
        if not rel_answers:
            # Fallback to legacy JSON evaluation
            return self._evaluate_legacy(user_answers)

        answer_groups = group_answers_by_blank(rel_answers)
        num_blanks = len(answer_groups)
        
        if len(user_answers) != num_blanks:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Incomplete input count"})

        correct_count = 0
        primary_feedback = []

        for i in sorted(answer_groups.keys()):
            user_val = str(user_answers[i] or "").strip()
            targets = answer_groups[i]
            
            is_match = False
            best_feedback = ""
            
            for target in targets:
                target_text = resolve_answer_text(target, lang)
                
                if target.is_primary and not best_feedback:
                    best_feedback = target_text
                
                nu = normalize_text(user_val, target.case_sensitive, target.ignore_punctuation)
                nt = normalize_text(target_text, target.case_sensitive, target.ignore_punctuation)
                
                if nt and nu == nt:
                    is_match = True
                    break
            
            primary_feedback.append(best_feedback)
            if is_match:
                correct_count += 1

        is_correct = correct_count == num_blanks
        return EvaluationResult(
            is_correct=is_correct,
            score=100 if is_correct else int((correct_count / num_blanks) * 100),
            feedback={"acceptable_answers": primary_feedback} if not is_correct else {}
        )

    def _evaluate_legacy(self, user_answers: List[Any]) -> EvaluationResult:
        # Re-implementation of old logic for backward compatibility
        if not isinstance(user_answers, list) or not user_answers:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Answers must be a non-empty list"})

        target_answers = self.step_detail.acceptable_answers
        if len(user_answers) != len(target_answers):
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Incomplete answers"})

        correct_count = 0
        for i, user_ans in enumerate(user_answers):
            target = target_answers[i]
            user_ans_clean = str(user_ans).strip().lower()

            if isinstance(target, list):
                if user_ans_clean in [str(t).strip().lower() for t in target]:
                    correct_count += 1
            else:
                if user_ans_clean == str(target).strip().lower():
                    correct_count += 1

        is_correct = correct_count == len(target_answers)
        score = 100 if is_correct else int((correct_count / len(target_answers)) * 100)

        return EvaluationResult(
            is_correct=is_correct, 
            score=score, 
            feedback={"acceptable_answers": target_answers} if not is_correct else {}
        )


class MatchPairsEvaluator(BaseStepEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        submitted_pairs = client_payload.get('pairs', [])  # list of {left_id, right_id}
        if not submitted_pairs:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "No pairs submitted"})

        actual_pairs = list(self.step_detail.pairs.all())
        if len(submitted_pairs) != len(actual_pairs):
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Incomplete mapping"})

        correct_count = 0
        for pair in actual_pairs:
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


class TypeTranslationEvaluator(FillBlankEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        user_text = client_payload.get('text', '')
        if not user_text:
            return EvaluationResult(is_correct=False, score=0, feedback={"error": "Text is empty"})
        
        # Delegate matching to FillBlank logic by wrapping the single input as a list
        payload_override = {**client_payload, 'answers': [user_text]}
        return super().evaluate(payload_override)


class SpeakPhraseEvaluator(BaseStepEvaluator):
    def evaluate(self, client_payload: Dict[str, Any]) -> EvaluationResult:
        score = client_payload.get('score', 0)
        is_correct = score >= self.step_detail.min_score_required
        
        return EvaluationResult(
            is_correct=is_correct,
            score=score,
            feedback=client_payload.get('feedback', {})
        )
