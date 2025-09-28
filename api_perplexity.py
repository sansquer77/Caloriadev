import base64
import requests
import os
from typing import Optional, Dict

API_KEY = os.getenv('PERPLEXITY_API_KEY')
API_URL = 'https://api.perplexity.ai/v1/image'

def encode_image_to_base64(image_bytes: bytes) -> str:
    """Converte bytes da imagem para string base64."""
    return base64.b64encode(image_bytes).decode('utf-8')

def analyze_meal_photo(image_bytes: bytes) -> Optional[Dict[str, float]]:
    """
    Envia foto codificada para API Perplexity e retorna estimativa
    dos macro nutrientes e calorias no formato:
    {
        'calories': float,
        'protein': float,
        'fat': float,
        'carbs': float,
        'sugar': float
    }
    """
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    img_base64 = encode_image_to_base64(image_bytes)
    prompt = (
        "Analise esta imagem de prato e me informe a estimativa de quantidade e "
        "calorias, explicitando proteínas, gorduras, carboidratos e açúcares somente."
    )
    data = {
        "image_base64": img_base64,
        "prompt": prompt
    }

    response = requests.post(API_URL, json=data, headers=headers)
    if response.status_code == 200:
        result = response.json()
        # Parse resultado baseado em estrutura esperada da API da Perplexity
        nutrients = {
            'calories': float(result.get('calories', 0)),
            'protein': float(result.get('protein', 0)),
            'fat': float(result.get('fat', 0)),
            'carbs': float(result.get('carbs', 0)),
            'sugar': float(result.get('sugar', 0))
        }
        return nutrients
    return None
