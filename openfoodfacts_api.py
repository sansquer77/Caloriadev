"""
Módulo para integração com a API Open Food Facts.
API gratuita com milhões de produtos, incluindo muitos brasileiros.
Suporta busca por nome e código de barras.

Documentação: https://openfoodfacts.github.io/openfoodfacts-server/api/
"""

import requests
from typing import Optional, Dict, List
import re

# URL base da API Open Food Facts
OFF_API_URL = "https://world.openfoodfacts.org/api/v2"
OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product"

# User-Agent obrigatório pela API
HEADERS = {
    'User-Agent': 'CaloriaApp/1.0 (https://github.com/caloriadev) - Contact: app@caloria.dev'
}


def search_product_by_barcode(barcode: str) -> Optional[Dict]:
    """
    Busca produto pelo código de barras.
    
    Args:
        barcode: Código de barras do produto (EAN-13, UPC, etc.)
    
    Returns:
        Dicionário com dados nutricionais ou None se não encontrado.
    """
    # Limpar código de barras
    barcode = re.sub(r'[^0-9]', '', barcode)
    
    if not barcode or len(barcode) < 8:
        return None
    
    try:
        url = f"{OFF_PRODUCT_URL}/{barcode}.json"
        response = requests.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') == 1 and 'product' in data:
                product = data['product']
                return _parse_product(product)
        
        return None
        
    except Exception as e:
        print(f"Erro ao buscar produto por código de barras: {e}")
        return None


def search_product_by_name(food_name: str, country: str = "brazil") -> Optional[Dict]:
    """
    Busca produto por nome.
    
    Args:
        food_name: Nome do alimento a buscar
        country: País para filtrar resultados (default: brazil)
    
    Returns:
        Dicionário com dados nutricionais ou None se não encontrado.
    """
    if not food_name or len(food_name.strip()) < 2:
        return None
    
    try:
        params = {
            'search_terms': food_name,
            'search_simple': 1,
            'action': 'process',
            'json': 1,
            'page_size': 5,
            'countries_tags_en': country,
            'fields': 'product_name,brands,nutriments,serving_size,nutrition_grades,image_url'
        }
        
        response = requests.get(OFF_SEARCH_URL, params=params, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            products = data.get('products', [])
            
            if products:
                # Tentar encontrar o melhor match
                best_product = _find_best_match(food_name, products)
                if best_product:
                    return _parse_product(best_product)
        
        # Se não encontrou no Brasil, tenta busca global
        if country == "brazil":
            return search_product_by_name(food_name, country="")
        
        return None
        
    except Exception as e:
        print(f"Erro ao buscar produto por nome: {e}")
        return None


def _find_best_match(search_term: str, products: List[Dict]) -> Optional[Dict]:
    """Encontra o melhor match entre os produtos retornados."""
    if not products:
        return None
    
    search_lower = search_term.lower()
    
    # Primeiro, procura match exato no nome
    for product in products:
        name = product.get('product_name', '').lower()
        if search_lower in name or name in search_lower:
            # Verifica se tem dados nutricionais
            if product.get('nutriments'):
                return product
    
    # Se não encontrou match exato, retorna o primeiro com dados nutricionais
    for product in products:
        if product.get('nutriments'):
            return product
    
    return products[0] if products else None


def _parse_product(product: Dict) -> Dict:
    """Converte dados do produto Open Food Facts para nosso formato."""
    nutriments = product.get('nutriments', {})
    
    # Extrair valores nutricionais por 100g
    calories = nutriments.get('energy-kcal_100g', 0)
    if not calories:
        # Converter de kJ para kcal se necessário
        energy_kj = nutriments.get('energy_100g', 0)
        calories = energy_kj / 4.184 if energy_kj else 0
    
    result = {
        'name': product.get('product_name', 'Produto'),
        'brand': product.get('brands', ''),
        'quantity': '100g',
        'calories': float(calories or 0),
        'protein': float(nutriments.get('proteins_100g', 0) or 0),
        'fat_total': float(nutriments.get('fat_100g', 0) or 0),
        'fat_saturated': float(nutriments.get('saturated-fat_100g', 0) or 0),
        'carbs': float(nutriments.get('carbohydrates_100g', 0) or 0),
        'sugar': float(nutriments.get('sugars_100g', 0) or 0),
        'fiber': float(nutriments.get('fiber_100g', 0) or 0),
        'sodium': float(nutriments.get('sodium_100g', 0) or 0) * 1000,  # Converter g para mg
        'potassium': float(nutriments.get('potassium_100g', 0) or 0) * 1000,
        'cholesterol': float(nutriments.get('cholesterol_100g', 0) or 0) * 1000,
        'source': 'Open Food Facts',
        'serving_size': product.get('serving_size', '100g'),
        'nutrition_grade': product.get('nutrition_grades', ''),
        'image_url': product.get('image_url', '')
    }
    
    return result


def get_nutrition_openfoodfacts(food_name: str, quantity_grams: float = 100.0, barcode: Optional[str] = None) -> Optional[Dict]:
    """
    Obtém dados nutricionais do Open Food Facts.
    
    Args:
        food_name: Nome do alimento
        quantity_grams: Quantidade em gramas
        barcode: Código de barras (opcional, tem prioridade)
    
    Returns:
        Dicionário com dados nutricionais ajustados ou None
    """
    result = None
    
    # Se tem código de barras, usa primeiro
    if barcode:
        result = search_product_by_barcode(barcode)
    
    # Se não encontrou por código de barras, busca por nome
    if not result:
        result = search_product_by_name(food_name)
    
    if not result:
        return None
    
    # Ajustar para a quantidade especificada
    factor = quantity_grams / 100.0
    
    return {
        'name': result.get('name', food_name),
        'brand': result.get('brand', ''),
        'quantity': f"{quantity_grams}g",
        'calories': result.get('calories', 0) * factor,
        'protein': result.get('protein', 0) * factor,
        'fat_total': result.get('fat_total', 0) * factor,
        'fat_saturated': result.get('fat_saturated', 0) * factor,
        'carbs': result.get('carbs', 0) * factor,
        'sugar': result.get('sugar', 0) * factor,
        'fiber': result.get('fiber', 0) * factor,
        'sodium': result.get('sodium', 0) * factor,
        'potassium': result.get('potassium', 0) * factor,
        'cholesterol': result.get('cholesterol', 0) * factor,
        'source': 'Open Food Facts',
        'nutrition_grade': result.get('nutrition_grade', ''),
        'original_name': result.get('name', '')
    }


def test_openfoodfacts():
    """Testa a integração com Open Food Facts."""
    print("=== Testando Open Food Facts ===")
    
    # Teste por nome
    print("\n1. Busca por nome: 'Coca-Cola'")
    result = get_nutrition_openfoodfacts("Coca-Cola", 350)
    if result:
        print(f"   ✅ Encontrado: {result['name']} ({result['brand']})")
        print(f"   Calorias: {result['calories']:.0f} kcal")
    else:
        print("   ❌ Não encontrado")
    
    # Teste por código de barras (Coca-Cola 350ml)
    print("\n2. Busca por código de barras: '7894900011517'")
    result = search_product_by_barcode("7894900011517")
    if result:
        print(f"   ✅ Encontrado: {result['name']}")
        print(f"   Calorias: {result['calories']:.0f} kcal/100g")
    else:
        print("   ❌ Não encontrado")
    
    # Teste produto brasileiro
    print("\n3. Busca por nome: 'Guaraná Antarctica'")
    result = get_nutrition_openfoodfacts("Guaraná Antarctica", 350)
    if result:
        print(f"   ✅ Encontrado: {result['name']}")
        print(f"   Calorias: {result['calories']:.0f} kcal")
    else:
        print("   ❌ Não encontrado")


if __name__ == "__main__":
    test_openfoodfacts()
