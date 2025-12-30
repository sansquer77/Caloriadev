"""
Portion size corrections for Brazilian food analysis.
Fixes common over/underestimation issues in nutritional calculations.

Problem: "uma xícara de café com leite" was being parsed as 240g,
but it should be ~180ml with milk, not pure liquid calories.

Solution: Apply common Brazilian portion corrections after parsing
to normalize quantities before API lookups.
"""

import re
from typing import Tuple, List

# Common Brazilian portion corrections
# Fixes incorrect weight estimates from generic patterns
PORTION_CORRECTIONS = {
    # Beverages (ml not treated as grams for calorie calculation)
    'café com leite': (180, 'liquid_beverage'),  # 180ml, not 240ml
    'café': (150, 'liquid_beverage'),  # Black coffee: 150ml
    'leite': (200, 'liquid'),  # 200ml
    'suco': (200, 'liquid'),  # Juice: 200ml
    'refrigerante': (250, 'liquid'),  # Soft drink: 250ml
    'chá': (150, 'liquid'),  # Tea: 150ml
    'água': (200, 'liquid'),  # Water: 200ml
    'cerveja': (350, 'liquid'),  # Beer: 350ml
    'vinho': (150, 'liquid'),  # Wine: 150ml
    'leite quente': (200, 'liquid'),  # Hot milk: 200ml
    'leite integral': (200, 'liquid'),  # Whole milk: 200ml
    'leite desnatado': (200, 'liquid'),  # Skim milk: 200ml
    'achocolatado': (200, 'liquid'),  # Chocolate milk: 200ml
    'café coado': (150, 'liquid'),  # Strained coffee: 150ml
    'espresso': (30, 'liquid'),  # Espresso shot: 30ml

    # Bread and carbs
    'pão francês': (50, 'bread'),  # French bread: 50g
    'pão de queijo': (50, 'bread'),  # Cheese bread: 50g (1 unit)
    'bolo': (80, 'bread'),  # Cake slice: 80g
    'biscoito': (30, 'bread'),  # Cookie: 30g
    'torrada': (20, 'bread'),  # Toast: 20g per slice
    'pão integral': (40, 'bread'),  # Whole wheat: 40g per slice
    'pão branco': (40, 'bread'),  # White bread: 40g per slice
    
    # Proteins
    'ovo': (50, 'protein'),  # Egg: 50g (1 unit)
    'frango': (100, 'protein'),  # Chicken (average serving): 100g
    'carne': (100, 'protein'),  # Meat: 100g
    'peixe': (100, 'protein'),  # Fish: 100g
    'queijo': (30, 'protein'),  # Cheese: 30g
    'requeijão': (30, 'protein'),  # Curd cheese: 30g
    'iogurte': (150, 'dairy'),  # Yogurt: 150g
    'ricota': (80, 'protein'),  # Ricotta: 80g
    
    # Vegetables
    'salada': (150, 'vegetable'),  # Salad: 150g
    'alface': (50, 'vegetable'),  # Lettuce: 50g
    'tomate': (100, 'vegetable'),  # Tomato: 100g
    'cenoura': (100, 'vegetable'),  # Carrot: 100g
    'batata': (150, 'vegetable'),  # Potato: 150g
    'batata doce': (150, 'vegetable'),  # Sweet potato: 150g
    'arroz': (150, 'carbs'),  # Rice (cooked): 150g
    'feijão': (150, 'legume'),  # Beans (cooked): 150g
    
    # Fats/Oils
    'manteiga': (10, 'fat'),  # Butter: 10g
    'óleo': (10, 'fat'),  # Oil: 10g
    'azeite': (10, 'fat'),  # Olive oil: 10g
}

# Category multipliers (how to handle liquid vs solid weights)
CATEGORY_DENSITY = {
    'liquid': 1.0,  # 1ml = 1g for calorie calculations
    'liquid_beverage': 0.8,  # Milk-based drinks are denser, adjust for actual content
    'bread': 1.0,
    'protein': 1.0,
    'dairy': 1.0,
    'vegetable': 1.0,
    'carbs': 1.0,
    'legume': 1.0,
    'fat': 1.0,
}

def apply_portion_correction(food_name: str, quantity: float) -> Tuple[str, float]:
    """
    Applies portion size corrections for known foods.
    
    Args:
        food_name: The food name (lowercase)
        quantity: The parsed quantity in grams
        
    Returns:
        Tuple of (corrected_food_name, corrected_quantity)
    """
    food_lower = food_name.lower().strip()
    
    # Check for exact matches first
    for known_food, (correct_quantity, category) in PORTION_CORRECTIONS.items():
        if food_lower == known_food:
            print(f"✅ Portion correction applied: {food_name} {quantity}g → {correct_quantity}g ({category})")
            return (food_name, correct_quantity)
    
    # Check for substring matches (for phrases like "1 xícara de café com leite")
    for known_food, (correct_quantity, category) in PORTION_CORRECTIONS.items():
        if known_food in food_lower:
            print(f"✅ Portion correction applied: {food_name} {quantity}g → {correct_quantity}g ({category})")
            return (food_name, correct_quantity)
    
    # No correction needed
    return (food_name, quantity)

def correct_portion_size(food_items: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    """
    Apply portion corrections to a list of food items.
    
    Args:
        food_items: List of (food_name, quantity_grams) tuples
        
    Returns:
        List of corrected (food_name, quantity_grams) tuples
    """
    corrected_items = []
    
    for food_name, quantity in food_items:
        corrected_name, corrected_qty = apply_portion_correction(food_name, quantity)
        corrected_items.append((corrected_name, corrected_qty))
    
    return corrected_items

def estimate_portion_grams(portion_phrase: str) -> float:
    """
    Estimate portion size in grams from common Brazilian descriptions.
    
    Examples:
        "uma xícara" → 250g (but may be corrected later based on content)
        "um prato" → 200g
        "uma fatia" → 30g
    
    Args:
        portion_phrase: Portuguese portion description
        
    Returns:
        Estimated quantity in grams
    """
    phrase = portion_phrase.lower().strip()
    
    # Common portion phrases
    portions = {
        'xícara': 240,
        'copo': 240,
        'cálice': 150,
        'prato': 200,
        'tigela': 300,
        'colher de sopa': 15,
        'colher de chá': 5,
        'fatia': 30,
        'pedaço': 30,
        'unidade': 100,
        'dúzia': 1200,
        'porção': 200,
    }
    
    for key, value in portions.items():
        if key in phrase:
            return value
    
    # Default to 100g if can't determine
    return 100.0
