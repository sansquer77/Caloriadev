"""
Módulo de integração com APIs de nutrição.
Fluxo: TACO (local) → Open Food Facts (API gratuita) → Perplexity AI (fallback)
Análise de imagens: Google Gemini (visão)
"""

import base64
import requests
import os
import json
import re
from typing import Optional, Dict, List, Tuple

# Carregar variáveis de ambiente do arquivo .env (se existir)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv não instalado, usar apenas variáveis de ambiente do sistema

# Importar módulo TACO
try:
    from taco_db import get_taco_nutrition, search_taco, init_taco_db, get_taco_stats
    TACO_AVAILABLE = True
except ImportError:
    TACO_AVAILABLE = False
    print("Módulo TACO não disponível")

    
try:
    from openfoodfacts_api import get_nutrition_openfoodfacts, search_product_by_barcode
    OPENFOODFACTS_AVAILABLE = True
except ImportError:
    OPENFOODFACTS_AVAILABLE = False
    print("Módulo Open Food Facts não disponível")

# Configurações da API Perplexity
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = 'https://api.perplexity.ai/chat/completions'
PERPLEXITY_MODEL = 'sonar'

# Configurações da API Google Gemini (para análise de imagens)
GEMINI_API_KEY = os.getenv('GEMINI_KEY')
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

# Timeouts para requisições (em segundos)
API_TIMEOUT_SHORT = 20
API_TIMEOUT_LONG = 45


def encode_image_to_base64(image_bytes: bytes) -> str:
    """Codifica imagem em base64 para envio à API."""
    return base64.b64encode(image_bytes).decode('utf-8')


def identify_items_gemini(image_bytes: bytes) -> Optional[Dict]:
    def extract_serving_size_from_label(text: str) -> str:
        """
        Extrai o serving_size do texto do rótulo usando padrões comuns.
        Retorna string como '40g', '50ml', etc, ou None se não encontrar.
        """
        serving_size_patterns = [
            r'(?:por[çc][aã]o|serving|tamanho)[\s:]*([0-9]+)\s*(g|gr|ml)',
            r'([0-9]+)\s*(g|gr|ml)\s*(?:por[çc][aã]o|serving)',
            r'([0-9]+)\s*(g|gr|ml)'
        ]
        for pattern in serving_size_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                unit = match.group(2) if len(match.groups()) > 1 else 'g'
                return f"{value}{unit}"
        return None
    """
    Analisa imagem de alimento usando Google Gemini Vision.
    
    Identifica:
    - Pratos/comidas: lista de alimentos com quantidade estimada em gramas
    - Produtos com rótulo: lê tabela nutricional diretamente
    
    Args:
        image_bytes: Bytes da imagem (JPEG ou PNG)
    
    Returns:
        Dicionário com:
        - 'type': 'food' ou 'label'
        - 'items': lista de alimentos identificados (para 'food')
        - 'description': descrição dos alimentos
        - 'nutrients': dados nutricionais lidos do rótulo (para 'label')
        Ou None se falhar
    """
    if not GEMINI_API_KEY:
        print("Erro: GEMINI_KEY não configurada")
        return None
    
    img_base64 = encode_image_to_base64(image_bytes)
    
    prompt = """
Você é um nutricionista especializado em LEITURA DE RÓTULOS NUTRICIONAIS.

Analise esta imagem cuidadosamente:

== SE FOR UM PRODUTO COM TABELA NUTRICIONAL VISÍVEL ==
VOCÊ DEVE LER OS NÚMEROS da tabela nutricional na imagem!
Procure valores como: Valor energético (kcal), Carboidratos (g), Proteínas (g), Gorduras (g), Sódio (mg), etc.

- SEMPRE extrair 'serving_size' do rótulo em formato 'Xg' ou 'Xml'. Procure por padrões como "40g", "porção 50ml", "serving 30g".
- Se NÃO conseguir ler os nutrientes, retorne 'nutrients': null (não zeros, não objeto vazio).

Retorne JSON com os valores NUMÉRICOS que você consegue ler:
{"type": "label", "product_name": "nome", "brand": "marca", "serving_size": "porção", "nutrients": {"calories": NUMERO, "protein": NUMERO, "carbs": NUMERO, "sugar": NUMERO, "fat_total": NUMERO, "fat_saturated": NUMERO, "fiber": NUMERO, "sodium": NUMERO}}

EXEMPLO de resposta correta:
{"type": "label", "product_name": "Iogurte Grego", "brand": "Vigor", "serving_size": "90g", "nutrients": {"calories": 159, "protein": 5.4, "carbs": 18, "sugar": 15, "fat_total": 7.2, "fat_saturated": 4.5, "fiber": 0, "sodium": 45}}

== SE FOR UM PRATO OU COMIDA SEM RÓTULO ==
Identifique os alimentos e estime as porções em gramas:
{"type": "food", "description": "descrição do prato", "items": [{"name": "arroz branco", "quantity_grams": 150}, {"name": "feijão", "quantity_grams": 100}]}

- Para alimentos em foto, inclua estimativa de PESO REAL (em gramas) do alimento na imagem, não apenas porção padrão.

== REGRAS ==
- NUNCA retorne nutrients vazio {} - sempre inclua os números que conseguir ler
- Se não conseguir ler um valor, use 0
- Se não conseguir ler NENHUM nutriente, retorne 'nutrients': null
- Para sódio em mg, converta para número (ex: "45mg" → 45)
- Retorne APENAS JSON, sem explicações
- Se não conseguir identificar: {"type": "unknown", "error": "mensagem"}
"""

    # Preparar request para Gemini
    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": img_base64
                        }
                    },
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024
        }
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=API_TIMEOUT_LONG)
        print(f"Gemini Vision Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()

            # Extrair texto da resposta
            candidates = result.get('candidates', [])
            if candidates:
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if parts:
                    text = parts[0].get('text', '')
                    print(f"Gemini Response: {text[:300]}...")

                    # Tentar parsear JSON da resposta
                    try:
                        # Limpar resposta (remover markdown se houver)
                        text = text.strip()
                        if text.startswith('```json'):
                            text = text[7:]
                        if text.startswith('```'):
                            text = text[3:]
                        if text.endswith('```'):
                            text = text[:-3]
                        text = text.strip()

                        result_json = json.loads(text)
                        # Se for label e não veio serving_size, tentar extrair do texto
                        if isinstance(result_json, dict) and result_json.get('type') == 'label':
                            if not result_json.get('serving_size'):
                                serving_size = extract_serving_size_from_label(text)
                                if serving_size:
                                    result_json['serving_size'] = serving_size
                        return result_json
                    except json.JSONDecodeError as e:
                        print(f"Erro ao parsear JSON do Gemini: {e}")
                        # Tentar extrair JSON com regex
                        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
                        if json_match:
                            try:
                                result_json = json.loads(json_match.group())
                                if isinstance(result_json, dict) and result_json.get('type') == 'label':
                                    if not result_json.get('serving_size'):
                                        serving_size = extract_serving_size_from_label(text)
                                        if serving_size:
                                            result_json['serving_size'] = serving_size
                                return result_json
                            except:
                                pass
                        return None
        elif response.status_code == 400:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', '')
            if 'API key not valid' in error_msg:
                print("ERRO: Chave da API Gemini inválida!")
                return {'type': 'error', 'error': 'Chave da API Gemini inválida. Verifique se a GEMINI_KEY está correta no arquivo .env'}
            print(f"Erro Gemini API 400: {error_msg}")
            return None
        else:
            print(f"Erro Gemini API: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        print("Timeout ao chamar Gemini API")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao chamar Gemini API: {e}")
        return None
    except Exception as e:
        print(f"Exceção inesperada ao chamar Gemini API: {e}")
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
    
    prompt = f"""Extraia os valores nutricionais de "{meal_text}" priorizando estas fontes (nesta ordem):

1. Rótulo da embalagem brasileira (valores por 100g ou 100ml)
2. TBCA/TACO oficial (Tabela Brasileira de Composição de Alimentos)
3. Site oficial da marca (Yakult, Nestlé, Sadia, Coca-Cola, etc.)
4. USDA FoodData Central (apenas como último recurso)

REGRAS IMPORTANTES:
- Prioritize official sources, but if not available, use reliable secondary sources from nutrition databases (TACO, OFF, nutrition websites).. Use APENAS dados oficiais de rótulos ou tabelas.
- For processed/industrialized foods, accept label data or reliable nutritional websites as valid sources.
- Return "not_found": true ONLY if data cannot be found from ANY reliable source (not just official).

Retorne APENAS JSON neste formato:
{{"items":["{meal_text}"],"calories":0,"protein":0,"fat_total":0,"fat_saturated":0,"carbs":0,"sugar":0,"fiber":0,"sodium":0,"source":"nome da fonte","not_found":false}}

Se NÃO encontrar dados oficiais, retorne:
{{"items":["{meal_text}"],"not_found":true,"error":"Não encontrei dados nutricionais oficiais para este item."}}"""

    data = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 800,
        "temperature": 0.1
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, json=data, headers=headers, timeout=API_TIMEOUT_LONG)
        print(f"Perplexity Nutrition Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0].get('message', {}).get('content', '')
                print(f"Perplexity Response: {content[:300]}...")
                
                # Extrai JSON da resposta
                try:
                    # Tenta encontrar JSON na resposta
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                    if json_match:
                        nutrition_data = json.loads(json_match.group())
                    else:
                        nutrition_data = json.loads(content)
                    
                    # Verifica se encontrou dados oficiais
                    if nutrition_data.get('not_found', False):
                        error_msg = nutrition_data.get('error', 'Não encontrei dados nutricionais oficiais para este item.')
                        print(f"Item não encontrado: {error_msg}")
                        return {'error': error_msg}
                    
                    # Extrai itens
                    items_info = nutrition_data.get('items', [meal_text])
                    
                    # Extrai fonte dos dados
                    source = nutrition_data.get('source', 'Perplexity AI')
                    
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
                        'source': source
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
    
        # Aplicar correcoes de porcoes para alimentos conhecidos
    return items

KNOWN_BRANDS = [
    'yakult', 'nestle', 'nestlé', 'sadia', 'perdigao', 'perdigão', 'seara',
    'coca-cola', 'coca cola', 'pepsi', 'fanta', 'sprite', 'guarana', 'guaraná',
    'antarctica', 'brahma', 'skol', 'heineken', 'budweiser',
    'bauducco', 'visconti', 'oreo', 'trakinas', 'passatempo', 'club social',
    'danone', 'activia', 'vigor', 'itambe', 'itambé', 'parmalat', 'elegê', 'elege',
    'marata', 'yoki', 'camil', 'urbano', 'tio joao', 'tio joão',
    'hellmanns', "hellmann's", 'heinz', 'knorr', 'maggi',
    'delicia', 'delícia', 'qualy', 'doriana',
    'tang', 'clight', 'mid', 'frisco',
    'nescafe', 'nescafé', 'pilao', 'pilão', 'tres coracoes', 'três corações',
    'lacta', 'garoto', 'arcor', 'sonho de valsa', 'bis', 'diamante negro',
    'tang', 'ades', 'del valle', 'sufresh', 'kapo',
    'nissin', 'miojo', 'cup noodles',
    'toddy', 'nescau', 'ovomaltine',
    'mcdonalds', "mcdonald's", 'burger king', 'bk', 'subway', 'habibs', "habib's",
    'spoleto', 'giraffas', 'outback', 'madero',
]


def is_industrial_product(food_name: str) -> bool:
    """
    Verifica se o alimento é um produto industrializado de marca conhecida.
    Esses produtos devem ser buscados no Open Food Facts ou Perplexity,
    não na TACO que contém apenas alimentos genéricos.
    
    Args:
        food_name: Nome do alimento
        
    Returns:
        True se for produto industrializado de marca conhecida
    """
    name_lower = food_name.lower()
    
    # Verificar marcas conhecidas
    for brand in KNOWN_BRANDS:
        if brand in name_lower:
            return True
    
    return False


def get_nutrition_from_taco(food_items: List[Tuple[str, float]]) -> Dict:
    """
    Busca nutrição de múltiplos itens na TACO.
    Pula produtos industrializados de marcas conhecidas.
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
        # Pular produtos industrializados de marcas - buscar direto no OFF/Perplexity
        if is_industrial_product(food_name):
            print(f"⏩ Produto de marca detectado, pulando TACO: {food_name}")
            not_found_items.append((food_name, quantity))
            continue
            
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
    
    
    # Processar cada item isoladamente e somar os resultados
    total_nutrients = {
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
        'cholesterol': 0.0
    }
    
    for food_name, quantity in food_items:
        # Consultar Perplexity para cada item INDIVIDUALMENTE
        item_text = f"{quantity}g de {food_name}"
        print(f"🔍 Consultando Perplexity isoladamente: {item_text}")
        
        result = analyze_meal_with_perplexity(item_text)
        
        if result and 'error' not in result:
            # Somar nutrientes do item
            for key in total_nutrients:
                total_nutrients[key] += result.get(key, 0)
        else:
            error_msg = result.get('error', 'Erro desconhecido') if result else 'Erro na API'
            print(f"❌ Perplexity falhou para {item_text}: {error_msg}")
    
    # Se nenhum item teve sucesso, retornar erro
    if total_nutrients.get('calories', 0) == 0:
        return {
            'error': 'Não foi possível encontrar dados nutricionais para nenhum item no Perplexity.'
        }
    
    # Retornar resultado combinado
    result = {
        'calories': total_nutrients.get('calories', 0),
        'protein': total_nutrients.get('protein', 0),
        'fat_total': total_nutrients.get('fat_total', 0),
        'fat_saturated': total_nutrients.get('fat_saturated', 0),
        'fat_polyunsaturated': total_nutrients.get('fat_polyunsaturated', 0),
        'fat_monounsaturated': total_nutrients.get('fat_monounsaturated', 0),
        'carbs': total_nutrients.get('carbs', 0),
        'sugar': total_nutrients.get('sugar', 0),
        'fiber': total_nutrients.get('fiber', 0),
        'sodium': total_nutrients.get('sodium', 0),
        'potassium': total_nutrients.get('potassium', 0),
        'cholesterol': total_nutrients.get('cholesterol', 0),
        'items_detected': [f"{qty}g de {name}" for name, qty in food_items],
        'source': 'Perplexity (itens isolados)'
    }
    
    print(f"Resultado Perplexity (itens isolados): {result}")
    return result


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
    """
    Analisa foto de refeição usando Google Gemini Vision.
    
    Fluxo:
    1. Gemini identifica os alimentos ou lê rótulo nutricional
    2. Se for rótulo: retorna valores nutricionais diretamente
    3. Se for comida: busca cada item no fluxo TACO → Open Food Facts → Perplexity
    
    Args:
        image_bytes: Bytes da imagem (JPEG ou PNG)
    
    Returns:
        Dicionário com dados nutricionais ou erro
    """
    # Verificar se a chave Gemini está configurada
    if not GEMINI_API_KEY:
        return {
            'error': 'Chave da API Gemini (GEMINI_KEY) não configurada. '
                     'Configure a variável de ambiente ou adicione ao arquivo .env. '
                     'Obtenha sua chave em: https://aistudio.google.com/apikey'
        }
    
    # Usar Gemini para analisar a imagem
    gemini_result = identify_items_gemini(image_bytes)
    
    if not gemini_result:
        print("Não foi possível identificar itens na imagem com Gemini.")
        return {'error': 'Não foi possível identificar os alimentos na imagem. Verifique se a foto está clara e tente novamente.'}
    
    result_type = gemini_result.get('type', 'unknown')
    
    # Caso 0: Erro de API (ex: chave inválida)
    if result_type == 'error':
        return {'error': gemini_result.get('error', 'Erro na API Gemini.')}
    
    # Caso 1: Erro ou desconhecido
    if result_type == 'unknown':
        error_msg = gemini_result.get('error', 'Não foi possível identificar o alimento na imagem.')
        return {'error': error_msg}
    
    # Caso 2: Rótulo nutricional - usar valores diretamente
    if result_type == 'label':
        print("Gemini identificou rótulo nutricional")
        nutrients = gemini_result.get('nutrients', {})
        product_name = gemini_result.get('product_name', 'Produto')
        brand = gemini_result.get('brand', '')
        serving_size = gemini_result.get('serving_size', None)

        # Verificar se os nutrientes estão vazios ou zerados
        has_valid_nutrients = nutrients and (
            nutrients.get('calories', 0) > 0 or 
            nutrients.get('carbs', 0) > 0 or 
            nutrients.get('protein', 0) > 0
        )

        # Se Gemini não conseguiu ler os valores, buscar no Open Food Facts
        if not has_valid_nutrients:
            print(f"⚠️ Gemini não extraiu nutrientes do rótulo. Buscando '{product_name}' no Open Food Facts...")

            # Montar nome de busca com marca
            search_name = f"{product_name} {brand}".strip() if brand else product_name

            # Tentar extrair porção real do nome ou do serving_size
            serving_val = 100.0
            serving_unit = 'g'
            if serving_size:
                import re
                match = re.search(r'(\d+(?:\.\d+)?)\s*(g|gr|ml)', str(serving_size).lower())
                if match:
                    serving_val = float(match.group(1))
                    serving_unit = match.group(2)

            food_items = [(search_name, serving_val)]

            # Tentar Open Food Facts
            if OPENFOODFACTS_AVAILABLE:
                off_result = get_nutrition_from_openfoodfacts(food_items)
                if off_result.get('found_items'):
                    print(f"✅ Open Food Facts encontrou nutrientes para o rótulo")
                    off_nutrients = off_result.get('nutrients', {})

                    result = {
                        'calories': off_nutrients.get('calories', 0),
                        'protein': off_nutrients.get('protein', 0),
                        'fat_total': off_nutrients.get('fat_total', 0),
                        'fat_saturated': off_nutrients.get('fat_saturated', 0),
                        'fat_polyunsaturated': 0.0,
                        'fat_monounsaturated': 0.0,
                        'carbs': off_nutrients.get('carbs', 0),
                        'sugar': off_nutrients.get('sugar', 0),
                        'fiber': off_nutrients.get('fiber', 0),
                        'sodium': off_nutrients.get('sodium', 0),
                        'potassium': off_nutrients.get('potassium', 0),
                        'cholesterol': off_nutrients.get('cholesterol', 0),
                        'items_detected': [product_name],
                        'description': f"{product_name} ({brand})" if brand else product_name,
                        'source': 'Open Food Facts (via Gemini)',
                        'serving_size': serving_size or f'{serving_val}{serving_unit}',
                        'quantity_adjustment': True
                    }
                    print(f"Nutrientes do OFF: {result}")
                    return result

            # Tentar Perplexity como fallback final
            perplexity_result = get_nutrition_from_perplexity(food_items)
            if perplexity_result and 'error' not in perplexity_result:
                print(f"✅ Perplexity encontrou nutrientes para o rótulo")
                perplexity_result['items_detected'] = [product_name]
                perplexity_result['description'] = f"{product_name} ({brand})" if brand else product_name
                perplexity_result['source'] = 'Perplexity (via Gemini)'
                perplexity_result['serving_size'] = serving_size or '100g'
                perplexity_result['quantity_adjustment'] = True
                return perplexity_result

            # Se nada funcionou, retornar erro pedindo descrição melhor
            return {
                'error': f'Não encontrei dados nutricionais oficiais para "{product_name}". '
                         'A foto do rótulo não estava legível ou o produto não está cadastrado. '
                         'Use a aba "Descrever Refeição" e digite o nome completo do produto com a marca.'
            }

        # Adicionar campo para ajuste de quantidade
        result = {
            'calories': float(nutrients.get('calories', 0)),
            'protein': float(nutrients.get('protein', 0)),
            'fat_total': float(nutrients.get('fat_total', 0)),
            'fat_saturated': float(nutrients.get('fat_saturated', 0)),
            'fat_polyunsaturated': 0.0,
            'fat_monounsaturated': 0.0,
            'carbs': float(nutrients.get('carbs', 0)),
            'sugar': float(nutrients.get('sugar', 0)),
            'fiber': float(nutrients.get('fiber', 0)),
            'sodium': float(nutrients.get('sodium', 0)),
            'potassium': 0.0,
            'cholesterol': 0.0,
            'items_detected': [product_name],
            'description': f"{product_name} ({brand})" if brand else product_name,
            'source': 'Rótulo (Gemini Vision)',
            'serving_size': serving_size or '100g',
            'quantity_adjustment': True
        }

        print(f"Nutrientes do rótulo: {result}")
        return result
    
    # Caso 3: Comida/prato - buscar cada item no fluxo normal
    if result_type == 'food':
        print("Gemini identificou prato/comida")
        description = gemini_result.get('description', '')
        items = gemini_result.get('items', [])

        if not items:
            # Se não tem itens estruturados, usar descrição como texto
            if description:
                nutrients = analyze_meal_by_text(description)
                if nutrients and 'error' not in nutrients:
                    nutrients['description'] = description
                return nutrients
            return {'error': 'Não foi possível identificar os alimentos na imagem.'}

        # Permitir edição de quantidades para cada item
        for item in items:
            if 'quantity_grams' not in item or not isinstance(item['quantity_grams'], (int, float)):
                item['quantity_grams'] = 100

        # Adicionar campo especial para ajuste de quantidade
        result = {
            'type': 'food',
            'description': description,
            'items': items,
            'quantity_adjustment': True
        }
        return result
    
    return {'error': 'Tipo de imagem não reconhecido.'}


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
