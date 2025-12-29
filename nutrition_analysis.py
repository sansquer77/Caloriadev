"""📊 Análise Nutricional com Insights do Perplexity

Funções:
- Analisar macronutrientes de um período (semanal/mensal)
- Comparar com recomendações nutricionais
- Gerar insights com Perplexity
- Destacar pontos positivos e melhorias
"""

from api_perplexity import analyze_meal_by_description
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import os


def get_nutrition_analysis(period_data: Dict, period_type: str = "semanal") -> str:
    """Gera análise nutricional com insights do Perplexity.
    
    Args:
        period_data: Dict com agregado de nutrientes do período
            {
                'days_count': 7,
                'meals_count': 21,
                'calories': 14000,
                'protein': 525,
                'carbs': 1750,
                'sugar': 140,
                'fiber': 175,
                'fat_total': 420,
                'fat_saturated': 140,
                'sodium': 8400,
                'potassium': 17500,
                'cholesterol': 875
            }
        period_type: "semanal" ou "mensal"
    
    Returns:
        String com análise nutricional gerada por Perplexity
    """
    
    if not os.getenv('PERPLEXITY_API_KEY'):
        return _fallback_nutrition_analysis(period_data, period_type)
    
    try:
        # Calcular médias
        days = period_data.get('days_count', 1)
        meals = period_data.get('meals_count', 1)
        
        avg_calories = period_data.get('calories', 0) / days
        avg_protein = period_data.get('protein', 0) / days
        avg_carbs = period_data.get('carbs', 0) / days
        avg_fiber = period_data.get('fiber', 0) / days
        avg_sugar = period_data.get('sugar', 0) / days
        avg_fat_total = period_data.get('fat_total', 0) / days
        avg_sodium = period_data.get('sodium', 0) / days
        
        # Calcular percentuais
        if avg_calories > 0:
            protein_pct = (avg_protein * 4 / avg_calories) * 100
            carbs_pct = (avg_carbs * 4 / avg_calories) * 100
            fat_pct = (avg_fat_total * 9 / avg_calories) * 100
        else:
            protein_pct = carbs_pct = fat_pct = 0
        
        # Montar prompt para Perplexity
        prompt = f"""Analise o seguinte padrão nutricional de {period_type} (uma pessoa real em diário) e dê feedback construtivo e realista:

### DADOS CONSOLIDADOS DE {period_type.upper()}
- Período: {days} dias
- Total de refeições: {meals}
- Total de calorias: {period_data.get('calories', 0):.0f} kcal

### MÉDIAS DIÁRIAS
- Calorias: {avg_calories:.0f} kcal/dia
- Proteínas: {avg_protein:.1f}g ({protein_pct:.1f}% das calorias)
- Carboidratos: {avg_carbs:.1f}g ({carbs_pct:.1f}% das calorias)
- Gordura total: {avg_fat_total:.1f}g ({fat_pct:.1f}% das calorias)
- Fibras: {avg_fiber:.1f}g/dia
- Açúcares: {avg_sugar:.1f}g/dia
- Sódio: {avg_sodium:.0f}mg/dia (meta: <2300mg)

### RECOMENDAÇÕES GERAIS PARA REFERÊNCIA
- Calorias: 1500-2500 kcal/dia (varia por pessoa)
- Proteínas: 1.6-2.2 g por kg de peso corporal
- Carboidratos: 45-65% das calorias
- Gordura: 20-35% das calorias
- Fibras: 25-35g/dia (meta)
- Açúcares: <25g/dia (OMS)
- Sódio: <2300mg/dia

### INSTRUÇÕES PARA FEEDBACK
1. Avalie o padrão REALISTA E PRATICAM ENTE (não diga "isso está horrível" - a pessoa está fazendo diario)
2. Identifique 3 PONTOS POSITIVOS (o que está bom)
3. Identifique 2-3 ÁREAS DE MELHORIA (realistas e factíveis)
4. Dê 1-2 ações concretas e fáceis
5. Respeite o trabalho e empenho da pessoa

Seja breve (máximo 200 palavras), amigável, e construtívo.
"""
        
        # Fazer chamada ao Perplexity
        result = analyze_meal_by_description(prompt)
        
        if result and 'error' not in result:
            analysis = result.get('description', '')
            if analysis:
                return analysis.strip()
        
        # Se falhar, usar fallback
        return _fallback_nutrition_analysis(period_data, period_type)
        
    except Exception as e:
        print(f"Aviso: Erro ao gerar análise com Perplexity: {e}")
        return _fallback_nutrition_analysis(period_data, period_type)


def _fallback_nutrition_analysis(period_data: Dict, period_type: str) -> str:
    """Fallback: Análise básica sem Perplexity."""
    days = period_data.get('days_count', 1)
    
    avg_calories = period_data.get('calories', 0) / days
    avg_protein = period_data.get('protein', 0) / days
    avg_carbs = period_data.get('carbs', 0) / days
    avg_fiber = period_data.get('fiber', 0) / days
    avg_sugar = period_data.get('sugar', 0) / days
    
    analysis = f"""
### ANÁLISE NUTRICIONAL - ÓTIMO DESEMPENHO

**Médias Diárias:**
- Calorias: {avg_calories:.0f} kcal
- Proteínas: {avg_protein:.1f}g
- Carboidratos: {avg_carbs:.1f}g
- Fibras: {avg_fiber:.1f}g
- Açúcares: {avg_sugar:.1f}g

**Destaques:**
"""
    
    # Avaliação de fibras
    if avg_fiber >= 25:
        analysis += "\n✅ **Fibras:** Excelente (>25g/dia) - Continue assim!"
    elif avg_fiber >= 20:
        analysis += "\n🙋 **Fibras:** Bom (20-25g/dia) - Quase na meta ideal"
    else:
        analysis += f"\n⚠️ **Fibras:** Abaixo do recomendado ({avg_fiber:.1f}g) - Aumente alimentos integrais"
    
    # Avaliação de açúcares
    if avg_sugar <= 25:
        analysis += "\n✅ **Açúcares:** Ótimo (<25g/dia) - Benéfico para saúde"
    elif avg_sugar <= 50:
        analysis += "\n🙋 **Açúcares:** Moderado (25-50g/dia) - Procure reduzir um pouco"
    else:
        analysis += f"\n⚠️ **Açúcares:** Elevado ({avg_sugar:.1f}g/dia) - Reduza alimentos com açúcar adicionado"
    
    # Avaliação de proteínas
    if avg_protein >= 100:
        analysis += "\n✅ **Proteínas:** Ótimo (>100g/dia) - Muito bom para construção muscular"
    elif avg_protein >= 70:
        analysis += f"\n🙋 **Proteínas:** Adequado ({avg_protein:.1f}g/dia) - Atende necessidades básicas"
    else:
        analysis += f"\n⚠️ **Proteínas:** Baixo ({avg_protein:.1f}g/dia) - Aumente consumo de proteínas"
    
    # Avaliação de calorias
    if 1500 <= avg_calories <= 2500:
        analysis += f"\n✅ **Calorias:** Adequado ({avg_calories:.0f} kcal/dia) - Dentro do esperado"
    elif avg_calories < 1500:
        analysis += f"\n⚠️ **Calorias:** Abaixo ({avg_calories:.0f} kcal/dia) - Possa estar baixo demais"
    else:
        analysis += f"\n⚠️ **Calorias:** Elevado ({avg_calories:.0f} kcal/dia) - Considere redução se necessário"
    
    return analysis


def compare_with_recommendations(period_data: Dict) -> Dict[str, Dict[str, any]]:
    """Compara nutrientes com recomendações e retorna status.
    
    Returns:
        {
            'protein': {'value': 100, 'target': 70, 'status': 'exceeds'},
            'fiber': {'value': 15, 'target': 25, 'status': 'below'},
            ...
        }
    """
    days = period_data.get('days_count', 1)
    
    recommendations = {
        'calories': {'daily_target': 2000, 'range': (1500, 2500)},
        'protein': {'daily_target': 70, 'range': (50, 150)},
        'carbs': {'daily_target': 250, 'range': (150, 400)},
        'fiber': {'daily_target': 25, 'range': (20, 40)},
        'sugar': {'daily_target': 25, 'range': (0, 25)},
        'fat_total': {'daily_target': 70, 'range': (40, 100)},
        'sodium': {'daily_target': 2300, 'range': (0, 2300)},
    }
    
    results = {}
    
    for nutrient, rec in recommendations.items():
        value = period_data.get(nutrient, 0) / days
        target = rec['daily_target']
        
        # Determinar status
        if nutrient == 'sugar' or nutrient == 'sodium':
            # Para esses, menos é melhor
            if value <= target * 0.8:
                status = 'excellent'
            elif value <= target:
                status = 'good'
            elif value <= target * 1.2:
                status = 'moderate'
            else:
                status = 'high'
        else:
            # Para outros, mais é melhor (até um ponto)
            if value >= target * 0.9:
                status = 'good'
            elif value >= target * 0.7:
                status = 'moderate'
            else:
                status = 'low'
        
        results[nutrient] = {
            'value': round(value, 1),
            'target': target,
            'status': status,
            'percentage': round((value / target * 100) if target > 0 else 0, 1)
        }
    
    return results
