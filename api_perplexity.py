import base64
import requests
import os
import json
import re
from typing import Optional, Dict

PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = 'https://api.perplexity.ai/chat/completions'

CALORIENINJAS_API_KEY = os.getenv('CALORIENINJAS_API_KEY')
CALORIENINJAS_API_URL = 'https://api.calorieninjas.com/v1/nutrition'

def encode_image_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode('utf-8')

def identify_items_perplexity(image_bytes: bytes) -> Optional[str]:
    """Identifica itens alimentares na imagem usando a API de chat da Perplexity com visão."""
    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json'
    }
    img_base64 = encode_image_to_base64(image_bytes)
    
    prompt = (
        "Você é um nutricionista especialista. Analise esta imagem de comida e identifique "
        "TODOS os itens alimentares visíveis. Para cada item, estime a quantidade/porção. "
        "Responda APENAS com uma lista simples dos alimentos e quantidades, separados por vírgula. "
        "Exemplo: '1 porção de arroz branco, 100g de frango grelhado, salada de alface'. "
        "Seja específico nas quantidades para análise nutricional precisa."
    )
    
    data = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 500,
        "temperature": 0.2
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, json=data, headers=headers, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                message = result['choices'][0].get('message', {})
                description = message.get('content', '')
                return description.strip()
        else:
            print(f"Erro Perplexity API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exceção ao chamar Perplexity API: {e}")
    return None

def analyze_meal_by_text(meal_text: str) -> Optional[Dict]:
    """Analisa texto descrevendo alimentos usando CalorieNinjas API."""
    headers = {
        'X-Api-Key': CALORIENINJAS_API_KEY
    }
    params = {'query': meal_text}
    
    try:
        response = requests.get(CALORIENINJAS_API_URL, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            result = response.json()
            # Inicializa todos os nutrientes
            nutrients = {
                'calories': 0.0,
                'protein': 0.0,
                'fat_total': 0.0,
                'fat_saturated': 0.0,
                'fat_polyunsaturated': 0.0,
                'fat_monounsaturated': 0.0,
                'carbs': 0.0,
                'sugar': 0.0,
                'fiber': 0.0,
                'sodium': 0.0,
                'potassium': 0.0,
                'cholesterol': 0.0,
                'items_detected': []
            }
            
            for item in result.get('items', []):
                nutrients['calories'] += float(item.get('calories', 0))
                nutrients['protein'] += float(item.get('protein_g', 0))
                nutrients['fat_total'] += float(item.get('fat_total_g', 0))
                nutrients['fat_saturated'] += float(item.get('fat_saturated_g', 0))
                nutrients['carbs'] += float(item.get('carbohydrates_total_g', 0))
                nutrients['sugar'] += float(item.get('sugar_g', 0))
                nutrients['fiber'] += float(item.get('fiber_g', 0))
                nutrients['sodium'] += float(item.get('sodium_mg', 0))
                nutrients['potassium'] += float(item.get('potassium_mg', 0))
                nutrients['cholesterol'] += float(item.get('cholesterol_mg', 0))
                nutrients['items_detected'].append(item.get('name', 'desconhecido'))
            
            return nutrients
        else:
            print(f"Erro CalorieNinjas API: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exceção ao chamar CalorieNinjas API: {e}")
    return None

def analyze_meal_photo(image_bytes: bytes) -> Optional[Dict]:
    """Analisa foto de refeição: identifica itens e calcula nutrientes."""
    description = identify_items_perplexity(image_bytes)
    if not description:
        print("Não foi possível identificar itens na imagem.")
        return None
    
    print(f"Descrição identificada dos itens: {description}")
    nutrients = analyze_meal_by_text(description)
    
    if nutrients:
        nutrients['description'] = description
    
    return nutrients

def analyze_meal_by_description(description: str) -> Optional[Dict]:
    """Analisa refeição por descrição textual (sem foto)."""
    nutrients = analyze_meal_by_text(description)
    if nutrients:
        nutrients['description'] = description
    return nutrients
