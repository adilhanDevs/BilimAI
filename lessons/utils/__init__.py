def get_translation(group, lang_code, fallback_text=None):
    """
    Helper to get translated text from a TranslationGroup.
    Uses 'active_translations' attribute if it was prefetched.
    """
    if not group:
        return fallback_text
    
    # Check for prefetched translations
    active_translations = getattr(group, 'active_translations', None)
    if active_translations is not None:
        if active_translations:
            # We assume active_translations is already filtered by language in get_optimized_prefetches
            return active_translations[0].text
        return fallback_text
    
    # Fallback to manual DB lookup if not prefetched (not recommended for production lists)
    translation = group.translations.filter(language_id=lang_code).first()
    if translation:
        return translation.text
        
    return fallback_text
