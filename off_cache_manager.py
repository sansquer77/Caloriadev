"""🎯 Gerenciador de Cache Open Food Facts integrado ao Caloria.db

Mudança importante:
- ❌ Removido: OFF_CACHE.json em disco
- ✅ Adicionado: Tabela open_food_facts_cache em Caloria.db

Benefícios:
1. Um único arquivo de backup (Caloria.db)
2. ACID compliance (transações seguras)
3. Sem limite de tamanho (JSON era limitado a ~1500 itens)
4. Sincronização automática com backup
5. Rastreamento de acesso melhorado
6. Limpeza automática (LRU 90 dias)
"""

from datetime import datetime, timedelta
from db import get_db_session, OpenFoodFactsCache
from sqlalchemy import func, desc
import json


def add_to_cache(food_data: dict) -> bool:
    """Adiciona ou atualiza item no cache do OFF.
    
    Args:
        food_data: Dict com as informações do produto
            {
                'food_name': str,
                'barcode': str (opcional),
                'product_name': str,
                'brand': str,
                'calories': float,
                'protein': float,
                'fat_total': float,
                'fat_saturated': float,
                'carbs': float,
                'sugar': float,
                'fiber': float,
                'sodium': float,
                'potassium': float,
                'cholesterol': float,
                'nutrition_grade': str,
                'serving_size': str,
                'image_url': str
            }
    
    Returns:
        bool: True se adicionado/atualizado, False se erro
    """
    try:
        with get_db_session() as session:
            # Normalizar food_name para busca (lowercase, trim)
            food_name_normalized = (food_data.get('food_name', '') or '').strip().lower()
            
            if not food_name_normalized and not food_data.get('barcode'):
                return False
            
            # Tentar encontrar por barcode (mais específico)
            if food_data.get('barcode'):
                cached = session.query(OpenFoodFactsCache).filter_by(
                    barcode=food_data['barcode']
                ).first()
                if cached:
                    # Atualizar
                    cached.hits += 1
                    cached.accessed_at = datetime.utcnow()
                    cached.product_name = food_data.get('product_name', cached.product_name)
                    # Atualizar nutrientes
                    for nutrient in ['calories', 'protein', 'fat_total', 'fat_saturated',
                                     'carbs', 'sugar', 'fiber', 'sodium', 'potassium', 'cholesterol']:
                        if nutrient in food_data:
                            setattr(cached, nutrient, food_data[nutrient])
                    session.commit()
                    return True
            
            # Tentar encontrar por nome normalizado
            cached = session.query(OpenFoodFactsCache).filter(
                func.lower(func.trim(OpenFoodFactsCache.food_name)) == food_name_normalized
            ).first()
            
            if cached:
                # Atualizar
                cached.hits += 1
                cached.accessed_at = datetime.utcnow()
                if food_data.get('barcode'):
                    cached.barcode = food_data['barcode']
                cached.product_name = food_data.get('product_name', cached.product_name)
                # Atualizar nutrientes
                for nutrient in ['calories', 'protein', 'fat_total', 'fat_saturated',
                                 'carbs', 'sugar', 'fiber', 'sodium', 'potassium', 'cholesterol']:
                    if nutrient in food_data:
                        setattr(cached, nutrient, food_data[nutrient])
                session.commit()
                return True
            
            # Criar novo item
            new_cache = OpenFoodFactsCache(
                food_name=food_data.get('food_name', ''),
                barcode=food_data.get('barcode'),
                product_name=food_data.get('product_name', ''),
                brand=food_data.get('brand'),
                calories=food_data.get('calories', 0),
                protein=food_data.get('protein', 0),
                fat_total=food_data.get('fat_total', 0),
                fat_saturated=food_data.get('fat_saturated', 0),
                carbs=food_data.get('carbs', 0),
                sugar=food_data.get('sugar', 0),
                fiber=food_data.get('fiber', 0),
                sodium=food_data.get('sodium', 0),
                potassium=food_data.get('potassium', 0),
                cholesterol=food_data.get('cholesterol', 0),
                nutrition_grade=food_data.get('nutrition_grade'),
                serving_size=food_data.get('serving_size'),
                image_url=food_data.get('image_url'),
                accessed_at=datetime.utcnow()
            )
            session.add(new_cache)
            session.commit()
            return True
            
    except Exception as e:
        print(f"❌ Erro ao adicionar item ao cache: {e}")
        return False


def get_from_cache(food_name: str = None, barcode: str = None) -> dict:
    """Busca item no cache.
    
    Args:
        food_name: Nome do alimento (busca parcial)
        barcode: Código de barras (busca exata)
    
    Returns:
        Dict com dados do item ou {} se não encontrado
    """
    try:
        with get_db_session() as session:
            query = session.query(OpenFoodFactsCache)
            
            if barcode:
                # Busca por barcode (exata e rápida)
                item = query.filter_by(barcode=barcode).first()
            elif food_name:
                # Busca por nome (normalizado)
                food_name_normalized = food_name.strip().lower()
                item = query.filter(
                    func.lower(func.trim(OpenFoodFactsCache.food_name)) == food_name_normalized
                ).first()
            else:
                return {}
            
            if item:
                # Atualizar last access
                item.accessed_at = datetime.utcnow()
                item.hits += 1
                session.commit()
                
                # Retornar como dict
                return {
                    'id': item.id,
                    'food_name': item.food_name,
                    'barcode': item.barcode,
                    'product_name': item.product_name,
                    'brand': item.brand,
                    'calories': item.calories,
                    'protein': item.protein,
                    'fat_total': item.fat_total,
                    'fat_saturated': item.fat_saturated,
                    'carbs': item.carbs,
                    'sugar': item.sugar,
                    'fiber': item.fiber,
                    'sodium': item.sodium,
                    'potassium': item.potassium,
                    'cholesterol': item.cholesterol,
                    'nutrition_grade': item.nutrition_grade,
                    'serving_size': item.serving_size,
                    'image_url': item.image_url,
                    'hits': item.hits
                }
            
            return {}
            
    except Exception as e:
        print(f"❌ Erro ao buscar item no cache: {e}")
        return {}


def get_off_cache_stats() -> dict:
    """Retorna estatísticas do cache OFF.
    
    Returns:
        {
            'status': 'ready',
            'total_items': int,
            'total_hits': int,
            'avg_hits_per_item': float,
            'estimated_size_mb': float,
            'expired_items': int,  # Sem acesso > 90 dias
            'top_items': [(name, hits), ...]
        }
    """
    try:
        with get_db_session() as session:
            total_items = session.query(func.count(OpenFoodFactsCache.id)).scalar() or 0
            
            if total_items == 0:
                return {
                    'status': 'ready',
                    'total_items': 0,
                    'total_hits': 0,
                    'avg_hits_per_item': 0,
                    'estimated_size_mb': 0,
                    'expired_items': 0,
                    'top_items': []
                }
            
            # Total de acessos
            total_hits = session.query(func.sum(OpenFoodFactsCache.hits)).scalar() or 0
            
            # Média de acessos por item
            avg_hits = float(total_hits) / total_items if total_items > 0 else 0
            
            # Itens expirados (90 dias sem acesso)
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            expired_items = session.query(func.count(OpenFoodFactsCache.id)).filter(
                OpenFoodFactsCache.accessed_at < cutoff_date
            ).scalar() or 0
            
            # Top 5 itens mais acessados
            top_items = session.query(
                OpenFoodFactsCache.product_name,
                OpenFoodFactsCache.hits
            ).order_by(desc(OpenFoodFactsCache.hits)).limit(5).all()
            
            # Estimar tamanho em MB (aproximado)
            # Cada registro: ~500 bytes (média)
            estimated_size_mb = (total_items * 500) / (1024 * 1024)
            
            return {
                'status': 'ready',
                'total_items': total_items,
                'total_hits': int(total_hits),
                'avg_hits_per_item': round(avg_hits, 2),
                'estimated_size_mb': round(estimated_size_mb, 2),
                'expired_items': expired_items,
                'top_items': [(str(name), hits) for name, hits in top_items]
            }
            
    except Exception as e:
        print(f"❌ Erro ao obter estatísticas: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'total_items': 0,
            'total_hits': 0,
            'avg_hits_per_item': 0,
            'estimated_size_mb': 0,
            'expired_items': 0,
            'top_items': []
        }


def get_off_cache_size() -> float:
    """Retorna tamanho estimado do cache em MB."""
    try:
        with get_db_session() as session:
            total_items = session.query(func.count(OpenFoodFactsCache.id)).scalar() or 0
            return round((total_items * 500) / (1024 * 1024), 2)
    except:
        return 0.0


def cleanup_off_cache(days_inactive: int = 90) -> int:
    """Remove itens não acessados há mais de X dias (LRU).
    
    Args:
        days_inactive: Número de dias sem acesso para remover (padrão: 90)
    
    Returns:
        int: Número de itens removidos
    """
    try:
        with get_db_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
            
            # Contar itens a remover
            to_remove = session.query(func.count(OpenFoodFactsCache.id)).filter(
                OpenFoodFactsCache.accessed_at < cutoff_date
            ).scalar() or 0
            
            # Remover
            session.query(OpenFoodFactsCache).filter(
                OpenFoodFactsCache.accessed_at < cutoff_date
            ).delete()
            
            session.commit()
            print(f"🧹 Limpeza de cache: {to_remove} itens removidos (inativos > {days_inactive} dias)")
            return to_remove
            
    except Exception as e:
        print(f"❌ Erro ao limpar cache: {e}")
        return 0


def clear_off_cache() -> bool:
    """Limpa TOTALMENTE o cache OFF (cuidado!).
    
    Returns:
        bool: True se bem-sucedido
    """
    try:
        with get_db_session() as session:
            count = session.query(func.count(OpenFoodFactsCache.id)).scalar() or 0
            session.query(OpenFoodFactsCache).delete()
            session.commit()
            print(f"⚠️  Cache OFF limpo completamente ({count} itens removidos)")
            return True
    except Exception as e:
        print(f"❌ Erro ao limpar cache: {e}")
        return False


def get_cache_health() -> dict:
    """Retorna informações sobre a saúde do cache.
    
    Returns:
        {
            'status': 'healthy' | 'warning' | 'critical',
            'total_items': int,
            'expired_ratio': float,  # Porcentagem de itens expirados
            'recommendation': str
        }
    """
    try:
        stats = get_off_cache_stats()
        total = stats['total_items']
        expired = stats['expired_items']
        
        if total == 0:
            return {
                'status': 'healthy',
                'total_items': 0,
                'expired_ratio': 0,
                'recommendation': 'Cache vazio - aguardando primeiro acesso'
            }
        
        expired_ratio = (expired / total) * 100
        
        if expired_ratio < 10:
            status = 'healthy'
            recommendation = '✅ Cache saudável'
        elif expired_ratio < 30:
            status = 'warning'
            recommendation = '⚠️  Cache com muitos itens inativos - considere limpeza'
        else:
            status = 'critical'
            recommendation = '🚨 Cache crítico - execute limpeza urgente'
        
        return {
            'status': status,
            'total_items': total,
            'expired_ratio': round(expired_ratio, 2),
            'recommendation': recommendation
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'total_items': 0,
            'expired_ratio': 0,
            'recommendation': '❌ Erro ao obter saúde do cache'
        }
