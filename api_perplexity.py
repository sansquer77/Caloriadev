import base64
import requests
import os
from typing import Optional, Dict

# Chaves das APIs via variável de ambiente
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = 'https://api.perplexity.ai/v1/image'

CALORIENINJAS_API_KEY = os.getenv('CALORIENINJAS_API_KEY')
CALORIENINJAS_API_URL = 'https://api.calorieninjas.com/v1/nutrition'

def encode_image_to_base64(image_bytes: bytes) -> str:
    """Converte bytes da imagem para string base64."""
    return base64.b64encode(image_bytes).decode('utf-8')

def identify_items_perplexity(image_bytes: bytes) -> Optional[str]:
    """
    Consulta a API do Perplexity para identificar e descrever itens da imagem.
    Deve retornar uma string descritiva contendo os itens e quantidades estimadas.
    """
    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json'
    }
    img_base64 = encode_image_to_base64(image_bytes)
    prompt = (
        "Identifique e descreva todos os itens alimentares nesta imagem, "
        "incluindo uma estimativa da quantidade/porção para cada item, "
        "formate a resposta em uma frase concisa em inglês que possa ser usada para análise nutricional."
    )
    data = {
        "image_base64": img_base64,
        "prompt": prompt
    }
    response = requests.post(PERPLEXITY_API_URL, json=data, headers=headers)

    if response.status_code == 200:
        result = response.json()
        # Assume que o resultado contem um campo 'text' ou similar com a descrição
        description = result.get('text', '') or result.get('answer', '') or ''
        return description.strip()
    return None

def analyze_meal_by_text(meal_text: str) -> Optional[Dict[str, float]]:
    """
    Consulta a API do CalorieNinjas com a string da descrição dos itens para retorno dos macros.
    """
    headers = {
        'X-Api-Key': CALORIENINJAS_API_KEY
    }
    params = {
        'query': meal_text
    }
    response = requests.get(CALORIENINJAS_API_URL, headers=headers, params=params)

    if response.status_code == 200:
        result = response.json()
        calories = protein = fat = carbs = sugar = 0.0
        for item in result.get('items', []):
            calories += float(item.get('calories', 0))
            protein += float(item.get('protein_g', 0))
            fat += float(item.get('fat_total_g', 0))
            carbs += float(item.get('carbohydrates_total_g', 0))
            sugar += float(item.get('sugar_g', 0))
        nutrients = {
            'calories': calories,
            'protein': protein,
            'fat': fat,
            'carbs': carbs,
            'sugar': sugar
        }
        return nutrients

    return None

def analyze_meal_photo(image_bytes: bytes) -> Optional[Dict[str, float]]:
    """
    Fluxo completo que identifica os itens na foto via Perplexity,
    depois consulta CalorieNinjas para obter os dados nutricionais.
    """
    description = identify_items_perplexity(image_bytes)
    if not description:
        return None
    # Opcional: log ou print da descrição para debug
    print(f"Descrição identificada dos itens: {description}")

    nutrients = analyze_meal_by_text(description)
    return nutrients
