"""🝴 Parser Inteligente de Refeições

Função:
- Recebe descrição de refeição (ex: "100g espaghetti, bife, salada, pudim")
- Usa Perplexity para quebrar em itens separados com quantidades
- Consulta cada item isoladamente para maior precisão
- Agrega os nutrientes
- Retorna itens individuais + totais

Benefícios:
- Maior precisão (cada item analisado isoladamente)
- Açúcares detectados corretamente (ex: pudim)
- Fibras mais precisas
- Rastreia itens individuais no banco de dados
"""

from api_perplexity import analyze_meal_by_description
from typing import List, Dict, Optional
import re
import os


def parse_meal_description(description: str) -> List[Dict]:
    """Quebra a descrição de refeição em itens separados usando Perplexity.
    
    Args:
        description: Descrição completa da refeição
            Ex: "100g espaghetti a alho e óleo, 1 bife médio à milanesa, salada, pudim"
    
    Returns:
        List de itens com quantidade normalizada
        [
            {'item': 'Espaghetti a alho e óleo', 'quantity': '100g'},
            {'item': 'Bife médio à milanesa', 'quantity': '150g'},
            {'item': 'Alface americana temperada', 'quantity': '80g'},
            {'item': 'Pudim de leite', 'quantity': '50g'}
        ]
    """
    perplexity_key = os.getenv('PERPLEXITY_API_KEY')
    if not perplexity_key:
        # Fallback: tentar parse simples por vírgulas
        return parse_meal_description_simple(description)
    
    try:
        # Prompt para Perplexity quebrar a refeição
        prompt = f"""Quebre a seguinte descrição de refeição em itens individuais com quantidades.

Descrição: {description}

Retorne APENAS um JSON com a seguinte estrutura (sem markdown):
{{
    "items": [
        {{
            "item": "nome do alimento completo",
            "quantity": "quantidade com unidade (g, ml, unção, xícara, etc)"
        }}
    ]
}}

Exemplos:
- "100g espaghetti a alho e óleo" → {{"item": "Espaghetti a alho e óleo", "quantity": "100g"}}
- "1 bife médio" → {{"item": "Bife médio", "quantity": "150g"}} (estimar se não souber)
- "porção de alface" → {{"item": "Alface americana", "quantity": "80g"}}

Se houver quantidades ambigúas, use tendências:
- "bife médio" ≈ 150g
- "prato cheio de arroz" ≈ 150g
- "xícara de suco" ≈ 250ml
- "pedaço pequeno" ≈ 50g
- "refeição normal" = estimar proporcões
"""
        
        # Fazer consulta ao Perplexity
        result = analyze_meal_by_description(prompt)
        
        if result and 'error' not in result:
            # Extrair JSON da resposta
            try:
                import json
                # Tenta extrair JSON da resposta
                response_text = result.get('description', '')
                
                # Buscar JSON na resposta
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    parsed = json.loads(json_str)
                    
                    items = parsed.get('items', [])
                    if items and len(items) > 0:
                        return items
            except (json.JSONDecodeError, AttributeError) as e:
                print(f"Aviso: Não consegui fazer parsing JSON: {e}")
                # Fallback para parse simples
                return parse_meal_description_simple(description)
        
        # Se falhar, usar fallback simples
        return parse_meal_description_simple(description)
        
    except Exception as e:
        print(f"Aviso: Erro ao fazer parsing com Perplexity: {e}")
        return parse_meal_description_simple(description)


def parse_meal_description_simple(description: str) -> List[Dict]:
    """Fallback: quebra por vírgulas e tenta extrair quantidades."""
    items = []
    
    # Dividir por vírgulas
    parts = [p.strip() for p in description.split(',')]
    
    for part in parts:
        if not part:
            continue
        
        # Tentar extrair quantidade (começa com número)
        quantity_match = re.match(r'(\d+(?:[.,]\d+)?\s*(?:g|ml|un|unção|xícara|colher|prato|pedaço|li|cc|ml))', part, re.IGNORECASE)
        
        if quantity_match:
            quantity = quantity_match.group(1).replace(',', '.')
            item_name = part[quantity_match.end():].strip()
        else:
            # Não tem quantidade explícita
            item_name = part
            quantity = None
        
        items.append({
            'item': item_name,
            'quantity': quantity or '100g'  # Padrão se não souber
        })
    
    return items


def analyze_meal_items(items: List[Dict]) -> Dict:
    """Analisa cada item isoladamente e agrega os nutrientes.
    
    Args:
        items: Lista de itens com nome e quantidade
    
    Returns:
        {
            'items': [
                {
                    'item': 'Espaghetti...',
                    'quantity': '100g',
                    'nutrients': {calories, protein, carbs, ...}
                }
            ],
            'totals': {calories, protein, carbs, ...}
        }
    """
    analyzed_items = []
    totals = {
        'calories': 0,
        'protein': 0,
        'carbs': 0,
        'sugar': 0,
        'fiber': 0,
        'fat_total': 0,
        'fat_saturated': 0,
        'sodium': 0,
        'potassium': 0,
        'cholesterol': 0
    }
    
    for item_data in items:
        item_name = item_data.get('item', '')
        quantity = item_data.get('quantity', '100g')
        
        if not item_name:
            continue
        
        # Construir consulta com quantidade
        query = f"{quantity} de {item_name}"
        
        # Analisar item isoladamente
        nutrients = analyze_meal_by_description(query)
        
        if nutrients and 'error' not in nutrients:
            # Item analisado com sucesso
            analyzed_item = {
                'item': item_name,
                'quantity': quantity,
                'nutrients': {
                    'calories': nutrients.get('calories', 0),
                    'protein': nutrients.get('protein', 0),
                    'carbs': nutrients.get('carbs', 0),
                    'sugar': nutrients.get('sugar', 0),
                    'fiber': nutrients.get('fiber', 0),
                    'fat_total': nutrients.get('fat_total', 0),
                    'fat_saturated': nutrients.get('fat_saturated', 0),
                    'sodium': nutrients.get('sodium', 0),
                    'potassium': nutrients.get('potassium', 0),
                    'cholesterol': nutrients.get('cholesterol', 0)
                }
            }
            analyzed_items.append(analyzed_item)
            
            # Agregar aos totais
            for key in totals:
                totals[key] += nutrients.get(key, 0)
        else:
            # Item não foi analisado
            analyzed_items.append({
                'item': item_name,
                'quantity': quantity,
                'nutrients': None,
                'error': 'Não foi possível analisar'
            })
    
    return {
        'items': analyzed_items,
        'totals': totals
    }


def parse_and_analyze_meal(description: str) -> Dict:
    """Pipe completo: parse → analisa isoladamente → agrega.
    
    Args:
        description: Descrição completa da refeição
    
    Returns:
        {
            'items': [{item, quantity, nutrients}, ...],
            'totals': {calories, protein, ...},
            'success': bool
        }
    """
    try:
        # Passo 1: Quebrar em itens
        items = parse_meal_description(description)
        
        if not items:
            return {
                'success': False,
                'error': 'Não consegui extrair itens da refeição',
                'items': [],
                'totals': {}
            }
        
        # Passo 2: Analisar cada item
        result = analyze_meal_items(items)
        
        result['success'] = True
        result['description'] = description
        result['item_count'] = len(result['items'])
        
        return result
        
    except Exception as e:
        print(f"❌ Erro ao fazer parse e análise: {e}")
        return {
            'success': False,
            'error': str(e),
            'items': [],
            'totals': {}
        }
