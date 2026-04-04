import re
import string
import unicodedata
from ..utils import get_translation

def normalize_text(text: str, case_sensitive: bool = False, ignore_punctuation: bool = True) -> str:
    """
    Standardized normalization for lesson answers.
    Handles Unicode normalization, whitespace, punctuation, and casing.
    """
    if text is None:
        return ""
    
    # Unicode normalization (NFKC handles compatibility characters)
    text = unicodedata.normalize('NFKC', str(text))
    
    # Strip whitespace
    text = text.strip()
    
    if not case_sensitive:
        text = text.lower()
        
    if ignore_punctuation:
        # Remove standard punctuation
        punct_re = re.compile('[%s]' % re.escape(string.punctuation))
        text = punct_re.sub('', text)
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
    return text

def resolve_answer_text(answer_obj, lang: str = 'en') -> str:
    """
    Resolves display text from a StepAnswer using the Content Ladder.
    """
    if answer_obj.translation_group:
        # Use existing helper to get localized text
        text = get_translation(answer_obj.translation_group, lang)
        if text:
            return text
            
    return answer_obj.text_fallback or ""

def group_answers_by_blank(answers_list):
    """
    Groups a prefetched list of StepAnswer objects by their blank_index.
    """
    grouped = {}
    for ans in answers_list:
        if ans.blank_index not in grouped:
            grouped[ans.blank_index] = []
        grouped[ans.blank_index].append(ans)
    return grouped
