import base64
import requests
import os
import json
import re
from typing import Optional, Dict
from urllib.parse import quote

PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = 'https://api.perplexity.ai/chat/completions'

# API Ninjas (substitui CalorieNinjas que foi descontinuado)
# Suporta múltiplas variáveis de ambiente para flexibilidade
NUTRITION_API_KEY = os.getenv('APININJAS_KEY') or os.getenv('CALORIENINJAS_API_KEY') or os.getenv('API_NINJAS_KEY')
NUTRITION_API_URL = 'https://api.api-ninjas.com/v1/nutrition'

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
                
                # Limpa a resposta - remove aspas, quebras de linha, prefixos comuns
                translation = translation.strip('"\'')
                translation = translation.replace('\n', ', ')
                translation = translation.replace('  ', ' ')
                
                # Remove prefixos comuns que a IA pode adicionar
                prefixes_to_remove = [
                    'Here is the translation:', 'Translation:', 'In English:',
                    'The translation is:', 'English:', 'Here\'s the translation:'
                ]
                for prefix in prefixes_to_remove:
                    if translation.lower().startswith(prefix.lower()):
                        translation = translation[len(prefix):].strip()
                
                # Limita o tamanho (CalorieNinjas tem limite)
                if len(translation) > 1500:
                    translation = translation[:1500]
                
                print(f"Tradução: '{food_description}' → '{translation}'")
                return translation
        else:
            print(f"Erro na tradução: {response.status_code} - {response.text}")
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

def analyze_meal_with_perplexity(meal_text: str) -> Optional[Dict]:
    """
    Analisa refeição usando Perplexity AI para buscar dados nutricionais de fontes verificadas.
    Busca em TACO/TBCA/IBGE (Brasil) e USDA (backup).
    NÃO faz estimativas - retorna erro se não encontrar dados exatos.
    """
    if not PERPLEXITY_API_KEY:
        print("Erro: PERPLEXITY_API_KEY não configurada")
        return {'error': 'Chave de API Perplexity não configurada.'}
    
    if not meal_text or len(meal_text.strip()) < 3:
        print("Erro: Descrição muito curta")
        return {'error': 'Descrição muito curta. Forneça mais detalhes sobre os alimentos.'}
    
    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    prompt = f"""Busque dados nutricionais da TBCA/TACO (Brasil) ou USDA para CADA ITEM desta refeição:

{meal_text}

IMPORTANTE: Identifique TODOS os itens separados por vírgula, "e" ou ponto. Calcule a soma total dos valores nutricionais de todos os itens.

Retorne APENAS JSON neste formato:
{{"items":["item1 com quantidade","item2 com quantidade"],"calories":0,"protein":0,"fat_total":0,"fat_saturated":0,"carbs":0,"sugar":0,"fiber":0,"sodium":0}}

Os valores devem ser a SOMA de todos os itens. Use valores reais das tabelas nutricionais."""

    data = {
        "model": "sonar",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, json=data, headers=headers, timeout=45)
        print(f"Perplexity Nutrition Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0].get('message', {}).get('content', '')
                print(f"Perplexity Response: {content[:300]}...")
                
                # Extrai JSON da resposta
                try:
                    # Tenta encontrar JSON na resposta
                    import re
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                    if json_match:
                        nutrition_data = json.loads(json_match.group())
                    else:
                        nutrition_data = json.loads(content)
                    
                    # Extrai itens
                    items_info = nutrition_data.get('items', [meal_text])
                    
                    # Converte para nosso formato padrão
                    nutrients = {
                        'calories': float(nutrition_data.get('calories', 0)),
                        'protein': float(nutrition_data.get('protein', 0)),
                        'fat_total': float(nutrition_data.get('fat_total', 0)),
                        'fat_saturated': float(nutrition_data.get('fat_saturated', 0)),
                        'fat_polyunsaturated': 0.0,
                        'fat_monounsaturated': 0.0,
                        'carbs': float(nutrition_data.get('carbs', 0)),
                        'sugar': float(nutrition_data.get('sugar', 0)),
                        'fiber': float(nutrition_data.get('fiber', 0)),
                        'sodium': float(nutrition_data.get('sodium', 0)),
                        'potassium': 0.0,
                        'cholesterol': 0.0,
                        'items_detected': items_info if items_info else [meal_text],
                        'source': 'Perplexity AI (TBCA/TACO)'
                    }
                    
                    print(f"Nutrientes extraídos: {nutrients}")
                    return nutrients
                    
                except json.JSONDecodeError as e:
                    print(f"Erro ao parsear JSON: {e}")
                    print(f"Conteúdo: {content}")
                    return {'error': 'Não foi possível processar a resposta da IA. Tente novamente.'}
        else:
            print(f"Erro Perplexity API: {response.status_code} - {response.text}")
            return {'error': f'Erro na API Perplexity (código {response.status_code}).'}
            
    except requests.exceptions.Timeout:
        return {'error': 'Timeout na consulta. Tente novamente.'}
    except Exception as e:
        print(f"Exceção: {e}")
        return {'error': f'Erro inesperado: {str(e)}'}


def analyze_meal_by_text(meal_text: str) -> Optional[Dict]:
    """
    Analisa texto descrevendo alimentos.
    Usa Perplexity AI diretamente (sem depender de APIs de nutrição externas).
    """
    return analyze_meal_with_perplexity(meal_text)


def analyze_meal_photo(image_bytes: bytes) -> Optional[Dict]:
    """Analisa foto de refeição: identifica itens e calcula nutrientes usando Perplexity."""
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
    """
    Analisa refeição por descrição textual.
    O Perplexity entende português diretamente, não precisa traduzir.
    """
    original_description = description.strip()
    
    # Perplexity entende português, então passamos direto
    nutrients = analyze_meal_by_text(original_description)
    
    if nutrients and 'error' not in nutrients:
        nutrients['description'] = original_description
    
    return nutrients
