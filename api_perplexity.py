import base64
import requests
import os
import json
import re
from typing import Optional, Dict, List, Tuple
from urllib.parse import quote

# Importar módulo TACO
try:
    from taco_db import get_taco_nutrition, search_taco, init_taco_db, get_taco_stats
    TACO_AVAILABLE = True
except ImportError:
    TACO_AVAILABLE = False
    print("Módulo TACO não disponível")

# Importar módulo Open Food Facts
try:
    from openfoodfacts_api import get_nutrition_openfoodfacts, search_product_by_barcode
    OPENFOODFACTS_AVAILABLE = True
except ImportError:
    OPENFOODFACTS_AVAILABLE = False
    print("Módulo Open Food Facts não disponível")

PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = 'https://api.perplexity.ai/chat/completions'


def encode_image_to_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode('utf-8')

def translate_food_to_english(food_description: str) -> Optional[str]:
    """
    Traduz descrição de alimentos do português para inglês usando Perplexity.
    Mantém quantidades no formato correto.
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
                
                # Limita o tamanho
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
    Retorna a descrição dos alimentos identificados."""
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


def parse_food_items(meal_text: str) -> List[Tuple[str, float]]:
    """
    Extrai itens alimentares e suas quantidades do texto.
    Retorna lista de tuplas (nome, quantidade_gramas).
    """
    items = []
    
    # Separar por vírgulas, "e", ponto e vírgula
    parts = re.split(r'[,;]|\s+e\s+', meal_text.lower())
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Tentar extrair quantidade
        quantity = 100.0  # Padrão: 100g
        food_name = part
        
        # Padrões de quantidade
        patterns = [
            (r'(\d+(?:\.\d+)?)\s*g\s+(?:de\s+)?(.+)', lambda m: (m.group(2), float(m.group(1)))),
            (r'(\d+(?:\.\d+)?)\s*(?:gramas?)\s+(?:de\s+)?(.+)', lambda m: (m.group(2), float(m.group(1)))),
            (r'(\d+)\s*(?:colher(?:es)?|col\.?)\s+(?:de\s+)?(?:sopa\s+)?(?:de\s+)?(.+)', lambda m: (m.group(2), float(m.group(1)) * 15)),  # 1 colher = ~15g
            (r'(\d+)\s*(?:colher(?:es)?|col\.?)\s+(?:de\s+)?(?:chá\s+)?(?:de\s+)?(.+)', lambda m: (m.group(2), float(m.group(1)) * 5)),  # 1 colher chá = ~5g
            (r'(\d+)\s*(?:fatia|pedaço)s?\s+(?:de\s+)?(.+)', lambda m: (m.group(2), float(m.group(1)) * 30)),  # 1 fatia = ~30g
            (r'(\d+)\s*(?:unidade|und\.?)s?\s+(?:de\s+)?(.+)', lambda m: (m.group(2), float(m.group(1)) * 100)),  # 1 unidade = ~100g
            (r'(\d+)\s*(?:copo|xícara)s?\s+(?:de\s+)?(.+)', lambda m: (m.group(2), float(m.group(1)) * 240)),  # 1 copo = ~240ml/g
            (r'(\d+)\s*(?:prato|porção|porções)s?\s+(?:de\s+)?(.+)', lambda m: (m.group(2), float(m.group(1)) * 200)),  # 1 prato = ~200g
        ]
        
        for pattern, extractor in patterns:
            match = re.search(pattern, part)
            if match:
                food_name, quantity = extractor(match)
                break
        
        # Limpar nome do alimento
        food_name = food_name.strip()
        food_name = re.sub(r'^(de|do|da|com)\s+', '', food_name)
        
        if food_name:
            items.append((food_name, quantity))
    
    return items


def get_nutrition_from_taco(food_items: List[Tuple[str, float]]) -> Dict:
    """
    Busca nutrição de múltiplos itens na TACO.
    Retorna dicionário com nutrients, found_items e not_found.
    """
    if not TACO_AVAILABLE:
        return {'nutrients': {}, 'found_items': [], 'not_found': food_items}
    
    total_nutrients = {
        'calories': 0.0,
        'protein': 0.0,
        'fat_total': 0.0,
        'fat_saturated': 0.0,
        'carbs': 0.0,
        'sugar': 0.0,
        'fiber': 0.0,
        'sodium': 0.0,
        'potassium': 0.0,
        'cholesterol': 0.0
    }
    
    found_items = []
    not_found_items = []
    
    for food_name, quantity in food_items:
        nutrition = get_taco_nutrition(food_name, quantity)
        
        if nutrition:
            print(f"✅ TACO encontrou: {food_name} → {nutrition.get('original_name', food_name)}")
            found_items.append({
                'name': food_name,
                'quantity': f"{quantity}g",
                'matched': nutrition.get('original_name', food_name),
                'source': 'TACO'
            })
            
            for key in total_nutrients:
                total_nutrients[key] += nutrition.get(key, 0)
        else:
            print(f"❌ TACO não encontrou: {food_name}")
            not_found_items.append((food_name, quantity))
    
    return {
        'nutrients': total_nutrients,
        'found_items': found_items,
        'not_found': not_found_items
    }


def get_nutrition_from_openfoodfacts(food_items: List[Tuple[str, float]], barcode: Optional[str] = None) -> Dict:
    """
    Busca nutrição de múltiplos itens na API Open Food Facts.
    Retorna dicionário com nutrients, found_items e not_found.
    """
    if not OPENFOODFACTS_AVAILABLE:
        return {'nutrients': {}, 'found_items': [], 'not_found': food_items}
    
    total_nutrients = {
        'calories': 0.0,
        'protein': 0.0,
        'fat_total': 0.0,
        'fat_saturated': 0.0,
        'carbs': 0.0,
        'sugar': 0.0,
        'fiber': 0.0,
        'sodium': 0.0,
        'potassium': 0.0,
        'cholesterol': 0.0
    }
    
    found_items = []
    not_found_items = []
    
    # Se tem código de barras, buscar primeiro
    if barcode and len(food_items) == 1:
        food_name, quantity = food_items[0]
        nutrition = get_nutrition_openfoodfacts(food_name, quantity, barcode=barcode)
        
        if nutrition:
            print(f"✅ Open Food Facts encontrou (barcode): {nutrition.get('original_name', food_name)}")
            found_items.append({
                'name': food_name,
                'quantity': f"{quantity}g",
                'matched': nutrition.get('original_name', food_name),
                'brand': nutrition.get('brand', ''),
                'source': 'Open Food Facts'
            })
            
            for key in total_nutrients:
                total_nutrients[key] += nutrition.get(key, 0)
            
            return {
                'nutrients': total_nutrients,
                'found_items': found_items,
                'not_found': []
            }
    
    # Buscar cada item por nome
    for food_name, quantity in food_items:
        nutrition = get_nutrition_openfoodfacts(food_name, quantity)
        
        if nutrition:
            print(f"✅ Open Food Facts encontrou: {food_name} → {nutrition.get('original_name', food_name)}")
            found_items.append({
                'name': food_name,
                'quantity': f"{quantity}g",
                'matched': nutrition.get('original_name', food_name),
                'brand': nutrition.get('brand', ''),
                'source': 'Open Food Facts'
            })
            
            for key in total_nutrients:
                total_nutrients[key] += nutrition.get(key, 0)
        else:
            print(f"❌ Open Food Facts não encontrou: {food_name}")
            not_found_items.append((food_name, quantity))
    
    return {
        'nutrients': total_nutrients,
        'found_items': found_items,
        'not_found': not_found_items
    }


def get_nutrition_from_perplexity(food_items: List[Tuple[str, float]]) -> Optional[Dict]:
    """
    Busca nutrição de itens usando Perplexity (fallback).
    """
    if not food_items:
        return None
    
    # Formatar texto dos itens
    items_text = ", ".join([f"{qty}g de {name}" for name, qty in food_items])
    
    return analyze_meal_with_perplexity(items_text)


def analyze_meal_by_text(meal_text: str, barcode: Optional[str] = None) -> Optional[Dict]:
    """
    Analisa texto descrevendo alimentos.
    
    Fluxo:
    1. Identifica os itens e quantidades no texto
    2. Busca cada item na tabela TACO (fonte primária - brasileira)
    3. Para itens não encontrados, busca no Open Food Facts (API gratuita global)
    4. Para itens ainda não encontrados, usa Perplexity (fallback final)
    5. Soma os valores nutricionais de todas as fontes
    """
    if not meal_text or len(meal_text.strip()) < 3:
        return {'error': 'Descrição muito curta. Forneça mais detalhes sobre os alimentos.'}
    
    print(f"\n=== Analisando: {meal_text} ===")
    if barcode:
        print(f"Código de barras: {barcode}")
    
    # 1. Extrair itens e quantidades
    food_items = parse_food_items(meal_text)
    print(f"Itens identificados: {food_items}")
    
    if not food_items:
        # Se não conseguiu extrair itens, usa Perplexity direto
        print("Não foi possível extrair itens, usando Perplexity diretamente...")
        return analyze_meal_with_perplexity(meal_text)
    
    # Se tem código de barras, tentar Open Food Facts primeiro
    if barcode:
        print(f"Buscando por código de barras no Open Food Facts: {barcode}")
        off_result = get_nutrition_from_openfoodfacts(food_items, barcode=barcode)
        
        if off_result.get('found_items'):
            found_items = off_result.get('found_items', [])
            total_nutrients = off_result.get('nutrients', {})
            
            result = {
                'calories': total_nutrients.get('calories', 0),
                'protein': total_nutrients.get('protein', 0),
                'fat_total': total_nutrients.get('fat_total', 0),
                'fat_saturated': total_nutrients.get('fat_saturated', 0),
                'fat_polyunsaturated': 0.0,
                'fat_monounsaturated': 0.0,
                'carbs': total_nutrients.get('carbs', 0),
                'sugar': total_nutrients.get('sugar', 0),
                'fiber': total_nutrients.get('fiber', 0),
                'sodium': total_nutrients.get('sodium', 0),
                'potassium': total_nutrients.get('potassium', 0),
                'cholesterol': total_nutrients.get('cholesterol', 0),
                'items_detected': [item.get('matched', item.get('name', '')) for item in found_items],
                'source': 'Open Food Facts'
            }
            
            print(f"Resultado (código de barras): {result}")
            return result
    
    # 2. Buscar na TACO primeiro
    taco_result = get_nutrition_from_taco(food_items)
    
    found_items = taco_result.get('found_items', [])
    not_found = taco_result.get('not_found', [])
    total_nutrients = taco_result.get('nutrients', {})
    
    sources = []
    if found_items:
        sources.append('TACO')
    
    # 3. Para itens não encontrados na TACO, buscar no Open Food Facts
    if not_found and OPENFOODFACTS_AVAILABLE:
        print(f"Buscando no Open Food Facts: {not_found}")
        off_result = get_nutrition_from_openfoodfacts(not_found)
        
        off_found = off_result.get('found_items', [])
        off_not_found = off_result.get('not_found', [])
        off_nutrients = off_result.get('nutrients', {})
        
        if off_found:
            sources.append('Open Food Facts')
            found_items.extend(off_found)
            
            # Somar nutrientes do Open Food Facts
            for key in total_nutrients:
                total_nutrients[key] = total_nutrients.get(key, 0) + off_nutrients.get(key, 0)
        
        # Atualizar lista de não encontrados
        not_found = off_not_found
    
    # 4. Para itens ainda não encontrados, usar Perplexity
    if not_found:
        print(f"Buscando no Perplexity: {not_found}")
        perplexity_result = get_nutrition_from_perplexity(not_found)
        
        if perplexity_result and 'error' not in perplexity_result:
            sources.append('Perplexity')
            
            # Somar nutrientes do Perplexity
            for key in total_nutrients:
                total_nutrients[key] = total_nutrients.get(key, 0) + perplexity_result.get(key, 0)
            
            # Adicionar itens encontrados pelo Perplexity
            perplexity_items = perplexity_result.get('items_detected', [])
            for item in perplexity_items:
                found_items.append({
                    'name': item if isinstance(item, str) else item.get('name', ''),
                    'source': 'Perplexity'
                })
    
    # 5. Verificar se encontrou algo
    if not found_items and not total_nutrients.get('calories', 0):
        # Fallback total: usar Perplexity para tudo
        print("Nenhum item encontrado, usando Perplexity para análise completa...")
        return analyze_meal_with_perplexity(meal_text)
    
    # 6. Montar resultado final
    source_str = ' + '.join(sources) if sources else 'Estimativa'
    
    result = {
        'calories': total_nutrients.get('calories', 0),
        'protein': total_nutrients.get('protein', 0),
        'fat_total': total_nutrients.get('fat_total', 0),
        'fat_saturated': total_nutrients.get('fat_saturated', 0),
        'fat_polyunsaturated': 0.0,
        'fat_monounsaturated': 0.0,
        'carbs': total_nutrients.get('carbs', 0),
        'sugar': total_nutrients.get('sugar', 0),
        'fiber': total_nutrients.get('fiber', 0),
        'sodium': total_nutrients.get('sodium', 0),
        'potassium': total_nutrients.get('potassium', 0),
        'cholesterol': total_nutrients.get('cholesterol', 0),
        'items_detected': [item.get('name', item) if isinstance(item, dict) else item for item in found_items],
        'source': source_str
    }
    
    print(f"Resultado final: {result}")
    return result


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


def analyze_meal_by_barcode(barcode: str, quantity_grams: float = 100.0) -> Optional[Dict]:
    """
    Analisa produto por código de barras usando Open Food Facts.
    
    Args:
        barcode: Código de barras do produto (EAN-13, UPC, etc.)
        quantity_grams: Quantidade consumida em gramas
    
    Returns:
        Dicionário com dados nutricionais ou erro
    """
    if not barcode or len(barcode.strip()) < 8:
        return {'error': 'Código de barras inválido. Deve ter pelo menos 8 dígitos.'}
    
    barcode = barcode.strip()
    print(f"\n=== Analisando código de barras: {barcode} ===")
    
    if not OPENFOODFACTS_AVAILABLE:
        return {'error': 'Módulo Open Food Facts não disponível.'}
    
    # Buscar no Open Food Facts
    nutrition = get_nutrition_openfoodfacts("Produto", quantity_grams, barcode=barcode)
    
    if nutrition:
        result = {
            'calories': nutrition.get('calories', 0),
            'protein': nutrition.get('protein', 0),
            'fat_total': nutrition.get('fat_total', 0),
            'fat_saturated': nutrition.get('fat_saturated', 0),
            'fat_polyunsaturated': 0.0,
            'fat_monounsaturated': 0.0,
            'carbs': nutrition.get('carbs', 0),
            'sugar': nutrition.get('sugar', 0),
            'fiber': nutrition.get('fiber', 0),
            'sodium': nutrition.get('sodium', 0),
            'potassium': nutrition.get('potassium', 0),
            'cholesterol': nutrition.get('cholesterol', 0),
            'items_detected': [nutrition.get('name', 'Produto')],
            'description': f"{nutrition.get('name', 'Produto')} ({nutrition.get('brand', '')})" if nutrition.get('brand') else nutrition.get('name', 'Produto'),
            'source': 'Open Food Facts',
            'nutrition_grade': nutrition.get('nutrition_grade', '')
        }
        
        print(f"Resultado (barcode): {result}")
        return result
    else:
        return {'error': f'Produto não encontrado para o código de barras: {barcode}. Tente descrever manualmente.'}


def analyze_meal_by_description(description: str, barcode: Optional[str] = None) -> Optional[Dict]:
    """
    Analisa refeição por descrição textual ou código de barras.
    O Perplexity entende português diretamente, não precisa traduzir.
    """
    # Se tem código de barras, usar análise específica
    if barcode:
        result = analyze_meal_by_barcode(barcode)
        if result and 'error' not in result:
            return result
        # Se falhou, continua com análise por texto
    
    original_description = description.strip()
    
    # Perplexity entende português, então passamos direto
    nutrients = analyze_meal_by_text(original_description)
    
    if nutrients and 'error' not in nutrients:
        nutrients['description'] = original_description
    
    return nutrients
