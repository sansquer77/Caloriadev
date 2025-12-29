"""💾 Gerenciador de Cache Open Food Facts em SQLite

Funções:
- add_to_cache(food_data) - Adiciona/atualiza item no cache
- get_from_cache(food_name, barcode) - Busca item no cache
- get_off_cache_stats() - Estatísticas do cache
- cleanup_off_cache(days_inactive=90) - Limpeza LRU
- get_cache_health() - Status do cache
"""

from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from db import SessionLocal, OpenFoodFactsCache
import logging

logger = logging.getLogger(__name__)


def add_to_cache(food_data: Dict[str, Any]) -> bool:
    """Adiciona ou atualiza um item no cache.
    
    Args:
        food_data: Dict com dados do alimento
            {
                'food_name': 'Maçã',
                'barcode': '7891234567890',
                'product_name': 'Maçã Red Delicious',
                'calories': 52.0,
                'protein': 0.3,
                'carbs': 14.0,
                'sugar': 10.0,
                'fiber': 2.4,
                ...
            }
    
    Returns:
        bool: True se sucesso, False se erro
    """
    try:
        db = SessionLocal()
        
        # Normalizar nome do alimento
        food_name = food_data.get('food_name', '').strip().lower()
        barcode = food_data.get('barcode', '').strip() or None
        
        if not food_name:
            logger.warning("Food name vazio ao tentar adicionar ao cache")
            return False
        
        # Verificar se já existe
        existing = db.query(OpenFoodFactsCache).filter(
            (OpenFoodFactsCache.food_name == food_name) |
            (OpenFoodFactsCache.barcode == barcode) if barcode else False
        ).first()
        
        if existing:
            # Atualizar
            existing.product_name = food_data.get('product_name')
            existing.brand = food_data.get('brand')
            existing.calories = food_data.get('calories', 0)
            existing.protein = food_data.get('protein', 0)
            existing.carbs = food_data.get('carbs', 0)
            existing.fat_total = food_data.get('fat_total', 0)
            existing.fat_saturated = food_data.get('fat_saturated', 0)
            existing.sugar = food_data.get('sugar', 0)
            existing.fiber = food_data.get('fiber', 0)
            existing.sodium = food_data.get('sodium', 0)
            existing.potassium = food_data.get('potassium', 0)
            existing.cholesterol = food_data.get('cholesterol', 0)
            existing.nutrition_grade = food_data.get('nutrition_grade')
            existing.serving_size = food_data.get('serving_size')
            existing.image_url = food_data.get('image_url')
            existing.accessed_at = datetime.utcnow()
            existing.hits += 1
            existing.include_in_backup = food_data.get('include_in_backup', True)
            
            db.commit()
            logger.info(f"Cache atualizado: {food_name}")
        else:
            # Criar novo
            cache_item = OpenFoodFactsCache(
                food_name=food_name,
                barcode=barcode,
                product_name=food_data.get('product_name'),
                brand=food_data.get('brand'),
                calories=food_data.get('calories', 0),
                protein=food_data.get('protein', 0),
                carbs=food_data.get('carbs', 0),
                fat_total=food_data.get('fat_total', 0),
                fat_saturated=food_data.get('fat_saturated', 0),
                sugar=food_data.get('sugar', 0),
                fiber=food_data.get('fiber', 0),
                sodium=food_data.get('sodium', 0),
                potassium=food_data.get('potassium', 0),
                cholesterol=food_data.get('cholesterol', 0),
                nutrition_grade=food_data.get('nutrition_grade'),
                serving_size=food_data.get('serving_size'),
                image_url=food_data.get('image_url'),
                cached_at=datetime.utcnow(),
                accessed_at=datetime.utcnow(),
                hits=1,
                include_in_backup=food_data.get('include_in_backup', True)
            )
            db.add(cache_item)
            db.commit()
            logger.info(f"Item adicionado ao cache: {food_name}")
        
        return True
    
    except Exception as e:
        logger.error(f"Erro ao adicionar ao cache: {e}")
        return False
    
    finally:
        db.close()


def get_from_cache(food_name: Optional[str] = None, barcode: Optional[str] = None) -> Optional[Dict]:
    """Busca um item no cache.
    
    Args:
        food_name: Nome do alimento (normalizado)
        barcode: Código de barras
    
    Returns:
        Dict com dados do alimento ou None
    """
    try:
        db = SessionLocal()
        
        query = db.query(OpenFoodFactsCache)
        
        if food_name:
            query = query.filter(OpenFoodFactsCache.food_name == food_name.strip().lower())
        elif barcode:
            query = query.filter(OpenFoodFactsCache.barcode == barcode.strip())
        else:
            return None
        
        result = query.first()
        
        if result:
            # Atualizar accessed_at e hits
            result.accessed_at = datetime.utcnow()
            result.hits += 1
            db.commit()
            
            # Retornar como dict
            return {
                'food_name': result.food_name,
                'barcode': result.barcode,
                'product_name': result.product_name,
                'brand': result.brand,
                'calories': result.calories,
                'protein': result.protein,
                'carbs': result.carbs,
                'fat_total': result.fat_total,
                'fat_saturated': result.fat_saturated,
                'sugar': result.sugar,
                'fiber': result.fiber,
                'sodium': result.sodium,
                'potassium': result.potassium,
                'cholesterol': result.cholesterol,
                'nutrition_grade': result.nutrition_grade,
                'serving_size': result.serving_size,
                'image_url': result.image_url
            }
        
        return None
    
    except Exception as e:
        logger.error(f"Erro ao buscar do cache: {e}")
        return None
    
    finally:
        db.close()


def get_off_cache_stats() -> Dict[str, Any]:
    """Retorna estatísticas do cache."""
    try:
        db = SessionLocal()
        
        total_items = db.query(func.count(OpenFoodFactsCache.id)).scalar() or 0
        total_hits = db.query(func.sum(OpenFoodFactsCache.hits)).scalar() or 0
        total_size_mb = (total_items * 0.0002)  # Estimativa: ~200 bytes por item
        
        # Último acesso
        last_access = db.query(func.max(OpenFoodFactsCache.accessed_at)).scalar()
        
        return {
            'total_items': total_items,
            'total_hits': total_hits,
            'estimated_size_mb': round(total_size_mb, 2),
            'last_accessed': last_access.isoformat() if last_access else None,
            'status': 'healthy' if total_items > 0 else 'empty'
        }
    
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas do cache: {e}")
        return {'error': str(e), 'status': 'error'}
    
    finally:
        db.close()


def cleanup_off_cache(days_inactive: int = 90) -> int:
    """Limpa itens inativos do cache (LRU).
    
    Args:
        days_inactive: Número de dias sem acesso para remover
    
    Returns:
        Número de itens removidos
    """
    try:
        db = SessionLocal()
        
        # Data limite
        cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
        
        # Contar itens a remover
        to_remove = db.query(OpenFoodFactsCache).filter(
            OpenFoodFactsCache.accessed_at < cutoff_date
        ).count()
        
        # Remover
        db.query(OpenFoodFactsCache).filter(
            OpenFoodFactsCache.accessed_at < cutoff_date
        ).delete()
        
        db.commit()
        logger.info(f"Cache limpo: {to_remove} itens removidos (>= {days_inactive} dias inativo)")
        
        return to_remove
    
    except Exception as e:
        logger.error(f"Erro ao limpar cache: {e}")
        return 0
    
    finally:
        db.close()


def clear_off_cache() -> bool:
    """Limpa TUDO o cache."""
    try:
        db = SessionLocal()
        db.query(OpenFoodFactsCache).delete()
        db.commit()
        logger.info("Cache completamente limpo")
        return True
    
    except Exception as e:
        logger.error(f"Erro ao limpar cache completo: {e}")
        return False
    
    finally:
        db.close()


def get_cache_health() -> Dict[str, Any]:
    """Retorna status de saúde do cache."""
    stats = get_off_cache_stats()
    
    if 'error' in stats:
        return {
            'status': 'critical',
            'message': f"Erro ao avaliar cache: {stats['error']}"
        }
    
    total_items = stats['total_items']
    estimated_size = stats['estimated_size_mb']
    
    if total_items == 0:
        status = 'empty'
        message = "Cache vazio"
    elif estimated_size > 500:  # > 500 MB
        status = 'critical'
        message = f"Cache muito grande ({estimated_size} MB) - considere limpeza"
    elif estimated_size > 200:  # > 200 MB
        status = 'warning'
        message = f"Cache está crescendo ({estimated_size} MB) - limpeza recomendada"
    else:
        status = 'healthy'
        message = f"Cache saudável ({total_items} itens, {estimated_size} MB)"
    
    return {
        'status': status,
        'message': message,
        'items': total_items,
        'size_mb': estimated_size
    }
