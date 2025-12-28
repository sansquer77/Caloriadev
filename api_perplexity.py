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

def translate_food_to_english(food_description: str) -> Optional[str]:
    """
    Traduz descrição de alimentos do português para inglês usando Perplexity.
    Mantém quantidades e formata para a API CalorieNinjas.
    """
    if not PERPLEXITY_API_KEY:
        print("Aviso: PERPLEXITY_API_KEY não configurada, usando descrição original")
        return food_description
    
    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""Traduza a seguinte descrição de alimentos do português para inglês.
Mantenha as quantidades exatas. Use termos culinários comuns em inglês.
Formate como uma lista simples separada por vírgulas.

Exemplos de tradução:
- "100g de arroz branco" → "100g white rice"
- "1 prato de feijão" → "1 cup black beans"
- "150g de frango grelhado" → "150g grilled chicken breast"
- "salada de alface com tomate" → "lettuce salad with tomato"
- "1 copo de suco de laranja" → "1 glass orange juice"
- "pão francês com manteiga" → "french bread roll with butter"
- "2 ovos fritos" → "2 fried eggs"
- "macarrão com molho de tomate" → "pasta with tomato sauce"

Descrição em português: {food_description}

Responda APENAS com a tradução em inglês, sem explicações adicionais."""

    data = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 300,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, json=data, headers=headers, timeout=20)
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                message = result['choices'][0].get('message', {})
                translation = message.get('content', '').strip()
                # Remove aspas se houver
                translation = translation.strip('"\'')
                print(f"Tradução: '{food_description}' → '{translation}'")
                return translation
        else:
            print(f"Erro na tradução: {response.status_code}")
    except Exception as e:
        print(f"Exceção na tradução: {e}")
    
    # Fallback: retorna original
    return food_description

def identify_items_perplexity(image_bytes: bytes) -> Optional[str]:
    """Identifica itens alimentares na imagem usando a API de chat da Perplexity com visão.
    Retorna a descrição já em inglês para compatibilidade com CalorieNinjas."""
    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json'
    }
    img_base64 = encode_image_to_base64(image_bytes)
    
    # Prompt modificado para retornar em inglês
    prompt = (
        "You are an expert nutritionist. Analyze this food image and identify "
        "ALL visible food items. For each item, estimate the quantity/portion. "
        "Respond ONLY with a simple comma-separated list of foods and quantities in ENGLISH. "
        "Example: '1 cup white rice, 100g grilled chicken breast, lettuce salad with tomato'. "
        "Be specific about quantities for accurate nutritional analysis."
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
    if not CALORIENINJAS_API_KEY:
        print("Erro: CALORIENINJAS_API_KEY não configurada")
        return {'error': 'Chave de API CalorieNinjas não configurada. Configure CALORIENINJAS_API_KEY.'}
    
    if not meal_text or len(meal_text.strip()) < 3:
        print("Erro: Descrição muito curta")
        return {'error': 'Descrição muito curta. Forneça mais detalhes sobre os alimentos.'}
    
    headers = {
        'X-Api-Key': CALORIENINJAS_API_KEY
    }
    params = {'query': meal_text.strip()}
    
    try:
        response = requests.get(CALORIENINJAS_API_URL, headers=headers, params=params, timeout=30)
        print(f"CalorieNinjas Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            items = result.get('items', [])
            print(f"Itens encontrados: {len(items)}")
            
            # Se não encontrou itens, retorna erro específico
            if not items:
                print(f"Nenhum item encontrado para: {meal_text}")
                return {'error': f'Nenhum alimento encontrado para "{meal_text}". Tente descrever os alimentos de forma diferente (ex: "100g chicken breast, 1 cup rice").'}
            
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
            
            for item in items:
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
        elif response.status_code == 401:
            print(f"Erro CalorieNinjas API: Autenticação falhou")
            return {'error': 'Chave de API CalorieNinjas inválida. Verifique a configuração.'}
        else:
            print(f"Erro CalorieNinjas API: {response.status_code} - {response.text}")
            return {'error': f'Erro na API CalorieNinjas (código {response.status_code}). Tente novamente.'}
    except requests.exceptions.Timeout:
        print("Timeout na chamada CalorieNinjas API")
        return {'error': 'Timeout na consulta. A API demorou muito para responder. Tente novamente.'}
    except Exception as e:
        print(f"Exceção ao chamar CalorieNinjas API: {e}")
        return {'error': f'Erro inesperado: {str(e)}'}

def analyze_meal_photo(image_bytes: bytes) -> Optional[Dict]:
    """Analisa foto de refeição: identifica itens e calcula nutrientes."""
    description = identify_items_perplexity(image_bytes)
    if not description:
        print("Não foi possível identificar itens na imagem.")
        return {'error': 'Não foi possível identificar os alimentos na imagem. Tente descrever manualmente.'}
    
    print(f"Descrição identificada dos itens: {description}")
    nutrients = analyze_meal_by_text(description)
    
    if nutrients and 'error' not in nutrients:
        nutrients['description'] = description
    
    return nutrients

def analyze_meal_by_description(description: str) -> Optional[Dict]:
    """Analisa refeição por descrição textual (sem foto).
    Traduz automaticamente do português para inglês antes de consultar CalorieNinjas."""
    
    # Guarda a descrição original em português
    original_description = description.strip()
    
    # Detecta se parece ser português e traduz se necessário
    # Palavras comuns em descrições de comida em português
    portuguese_indicators = [
        'de ', 'com ', 'arroz', 'feijão', 'frango', 'carne', 'salada', 
        'suco', 'pão', 'leite', 'ovo', 'batata', 'macarrão', 'queijo',
        'grelhado', 'frito', 'assado', 'cozido', 'porção', 'prato',
        'colher', 'xícara', 'copo', 'fatia', 'pedaço', 'tigela'
    ]
    
    text_lower = original_description.lower()
    is_portuguese = any(word in text_lower for word in portuguese_indicators)
    
    if is_portuguese:
        print(f"Detectado português, traduzindo: {original_description}")
        translated = translate_food_to_english(original_description)
        query_text = translated if translated else original_description
    else:
        print(f"Texto parece estar em inglês: {original_description}")
        query_text = original_description
    
    # Consulta CalorieNinjas com o texto traduzido
    nutrients = analyze_meal_by_text(query_text)
    
    if nutrients and 'error' not in nutrients:
        # Guarda a descrição original (em português) para exibição ao usuário
        nutrients['description'] = original_description
        # Guarda também o que foi enviado para a API (para debug)
        nutrients['query_sent'] = query_text
    
    return nutrients
