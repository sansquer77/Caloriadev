# Correcoes para Session State do Gemini

def safe_session_key(item_name: str, item_id: str = None) -> str:
    """Gera chave segura para session_state"""
    base = f"food_{hash(item_name)}_{item_id or 'default'}"
    return base.replace(" ", "_").replace("-", "_").replace("/", "_")[:50]

def process_gemini_food_items(gemini_result: dict):
    """Processa resultado Gemini com validacao de chaves"""
    safe_items = []
    
    if gemini_result.get("type") == "dish":
        for item in gemini_result.get("items", []):
            name = item.get("name", "alimento desconhecido")
            grams = item.get("grams", 100)
            
            nutrition = get_nutrition_complete(name, grams)
            if nutrition:
                safe_items.append({
                    "name": name,
                    "grams": grams,
                    "nutrition": nutrition,
                    "safe_key": safe_session_key(name)
                })
    
    return safe_items
