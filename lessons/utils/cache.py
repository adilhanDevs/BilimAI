from django.core.cache import cache
from ..utils import get_translation

# Cache TTL constants
TRANSLATION_TTL = 60 * 30  # 30 minutes
LESSON_STEP_TTL = 60 * 60  # 1 hour

def get_cached_translation(group_obj, lang: str) -> str:
    """
    Returns translation from prefetched data if available, falling back to cache, then DB.
    """
    if not group_obj:
        return ""

    # 1. Check for prefetched translations (avoids DB and cache overhead entirely)
    if hasattr(group_obj, 'active_translations'):
        for trans in group_obj.active_translations:
            # Depending on how the attr was set (prefetch_related to_attr)
            # It might be a list of Translation objects
            if hasattr(trans, 'language'):
                if trans.language.code == lang:
                    return trans.text
            elif hasattr(trans, 'language_id'):
                if trans.language_id == lang:
                    return trans.text
        return ""

    # 2. Check cache
    cache_key = f"trans_{group_obj.id}_{lang}"
    cached_text = cache.get(cache_key)
    if cached_text is not None:
        return cached_text

    # 3. Fallback to DB and populate cache
    text = get_translation(group_obj, lang)
    cache.set(cache_key, text, TRANSLATION_TTL)
    return text

def invalidate_lesson_cache(lesson_id: str):
    """
    Invalidate serialized lesson steps cache when updated.
    """
    cache.delete_pattern(f"lesson_steps_{lesson_id}_*")
