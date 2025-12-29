"""🤖 API do Google Gemini para Análise de Imagens de Refeição

Usa o modelo Gemini 1.5 Flash para analisar fotos de refeições e extrair:
- Itens identificados
- Quantidades estimadas
- Informações nutricionais
"""

import google.generativeai as genai
from PIL import Image
import io
import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

def analyze_meal_from_image(image_file, user_calorias_meta: float = 2000) -> Dict:
    """
    Analisa imagem de refeição com Google Gemini
    
    Params:
        image_file: Arquivo de imagem (PIL Image ou arquivo do Streamlit)
        user_calorias_meta: Meta de calorias do usuário (para contexto)
    
    Returns:
        Dict com:
            - success: bool
            - items: lista de itens identificados
            - totals: totais nutricionais
            - observation: observações adicionais
            - error: mensagem de erro (se houver)
    """
    try:
        # Configurar Gemini
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return {
                'success': False, 
                'error': '🔐 GEMINI_API_KEY não configurada. Verifique variáveis de ambiente.'
            }
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Converter para PIL se necessário
        if hasattr(image_file, 'read'):
            image_file.seek(0)
            image = Image.open(io.BytesIO(image_file.read()))
        else:
            image = image_file
        
        # Criar prompt detalhado para Gemini
        prompt = f"""
Você é um especialista em nutrição e diética. Analise esta foto de refeição e identifique:

1. ITENS INDIVIDUAIS de alimento vistos na foto
2. QUANTIDADE estimada de cada item (em gramas ou unidades)
3. INFORMAÇÕES NUTRICIONAIS de cada item (por porção estimada)

Contexto do usuário:
- Meta de calorias/dia: {user_calorias_meta} kcal

**IMPORTANTE:** Responda APENAS em JSON válido, sem texto antes ou depois:

{{
    "items": [
        {{
            "item": "nome do alimento",
            "quantity": "quantidade (ex: 150g, 1 unidade, 1 xicara)",
            "calories": número em kcal,
            "protein": número em gramas,
            "carbs": número em gramas,
            "fat": número em gramas,
            "fiber": número em gramas
        }}
    ],
    "observation": "observações adicionais sobre a refeição (origem, combinações, qualidade, etc)"
}}

Se não conseguir identificar com precisão, indique com "?" ou use estimativas conservadoras.
        """
        
        logger.info("[GEMINI] Analisando imagem de refeição...")
        
        # Enviar para Gemini
        response = model.generate_content([prompt, image])
        response_text = response.text
        
        logger.info(f"[GEMINI] Resposta: {response_text[:200]}...")
        
        # Limpar markdown backticks se existirem
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()
        
        # Extrair JSON
        result_data = json.loads(response_text)
        
        # Validar e processar itens
        processed_items = []
        for item in result_data.get('items', []):
            processed_item = {
                'item': str(item.get('item', 'Desconhecido')),
                'quantity': str(item.get('quantity', 'desconhecida')),
                'calories': float(item.get('calories', 0)),
                'protein': float(item.get('protein', 0)),
                'carbs': float(item.get('carbs', 0)),
                'fat': float(item.get('fat', 0)),
                'fiber': float(item.get('fiber', 0))
            }
            processed_items.append(processed_item)
        
        # Calcular totais
        totals = {
            'calories': sum(item.get('calories', 0) for item in processed_items),
            'protein': sum(item.get('protein', 0) for item in processed_items),
            'carbs': sum(item.get('carbs', 0) for item in processed_items),
            'fat': sum(item.get('fat', 0) for item in processed_items),
            'fiber': sum(item.get('fiber', 0) for item in processed_items)
        }
        
        logger.info(f"[GEMINI] Análise concluída. Total: {totals['calories']:.0f} kcal em {len(processed_items)} itens")
        
        return {
            'success': True,
            'items': processed_items,
            'totals': totals,
            'observation': result_data.get('observation', '')
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"[GEMINI] Erro ao fazer parse do JSON: {e}")
        return {
            'success': False, 
            'error': f"🔍 Erro ao processar resposta do Gemini: {e}"
        }
    except Exception as e:
        logger.error(f"[GEMINI] Erro ao analisar foto: {e}")
        return {
            'success': False, 
            'error': f"❌ Erro: {str(e)}"
        }
