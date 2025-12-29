"""
Gerenciador de Cache do Open Food Facts integrado ao banco principal.

✅ MELHORIAS implementadas:
- Cache salvo em caloria.db (banco principal) - sincroniza com backup
- Sem limite de 1500 itens (anterior)
- Limpeza inteligente (LRU): Remove itens não acessados há 90 dias
- Rastreamento de acesso para análise de uso
- Opção de excluir cache do backup se quiser economizar espaço
- Compartilhado entre todos os usuários

Arquitetura:
- taco.db: Apenas TACO (dados estáticos, não precisa backup)
- caloria.db: Tudo que precisa de backup (users, meals, cache OFF)
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
from db import get_db_session, OpenFoodFactsCache
from sqlalchemy import and_, func
import re


def normalize_food_name(name: str) -> str:
    """Normaliza nome do alimento para busca confiável."""
    if not name:
        return ""
    
    # Converter para minúsculas
    name = name.lower().strip()
    
    # Remover acentos
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', 'ñ': 'n'
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    
    # Remover caracteres especiais
    name = re.sub(r'[^\w\s]', '', name)
    
    # Remover espaços extras
    name = ' '.join(name.split())
    
    return name


def search_off_cache(food_name: Optional[str] = None, barcode: Optional[str] = None) -> Optional[Dict]:
    """
    Busca um alimento no cache do Open Food Facts.
    
    ✏️ MELHORADO:
    - Busca no banco principal (caloria.db)
    - Registra data de acesso para LRU (90 dias)
    - Incrementa contador de hits
    - Rápido com índices no banco
    
    Args:
        food_name: Nome do alimento
        barcode: Código de barras (tem prioridade)
    
    Returns:
        Dict com dados nutricionais ou None
    """
    with get_db_session() as session:
        cache_entry = None
        
        # Buscar por código de barras primeiro (mais exato)
        if barcode:
            barcode_clean = re.sub(r'[^0-9]', '', barcode)
            cache_entry = session.query(OpenFoodFactsCache).filter(
                OpenFoodFactsCache.barcode == barcode_clean
            ).first()
        
        # Se não encontrou por barcode, buscar por nome
        if not cache_entry and food_name:
            normalized = normalize_food_name(food_name)
            
            # Busca exata
            cache_entry = session.query(OpenFoodFactsCache).filter(
                OpenFoodFactsCache.food_name == normalized
            ).first()
            
            # Busca parcial se não encontrou exato
            if not cache_entry:
                cache_entry = session.query(OpenFoodFactsCache).filter(
                    OpenFoodFactsCache.food_name.ilike(f'%{normalized}%')
                ).order_by(OpenFoodFactsCache.hits.desc()).first()
        
        if cache_entry:
            # Atualizar metadados de acesso
            cache_entry.accessed_at = datetime.utcnow()
            cache_entry.hits += 1
            session.commit()
            
            # Retornar com flag de cache
            return {
                'name': cache_entry.product_name,
                'brand': cache_entry.brand or '',
                'barcode': cache_entry.barcode or '',
                'calories': cache_entry.calories,
                'protein': cache_entry.protein,
                'fat_total': cache_entry.fat_total,
                'fat_saturated': cache_entry.fat_saturated,
                'carbs': cache_entry.carbs,
                'sugar': cache_entry.sugar,
                'fiber': cache_entry.fiber,
                'sodium': cache_entry.sodium,
                'potassium': cache_entry.potassium,
                'cholesterol': cache_entry.cholesterol,
                'source': 'Open Food Facts (cache)',
                'cached': True,
                'hits': cache_entry.hits
            }
        
        return None


def save_to_off_cache(food_name: str, nutrition_data: Dict, barcode: Optional[str] = None) -> bool:
    """
    Salva um alimento no cache do Open Food Facts.
    
    ✏️ MELHORADO:
    - Salva em caloria.db (banco principal)
    - Sem limite de itens (antes: 1500)
    - Sincroniza automaticamente com backup
    - Campo include_in_backup permite controlar se vai para backup ou não
    
    Args:
        food_name: Nome usado na busca
        nutrition_data: Dados nutricionais
        barcode: Código de barras (opcional)
    
    Returns:
        True se salvou com sucesso
    """
    try:
        with get_db_session() as session:
            normalized = normalize_food_name(food_name)
            barcode_clean = re.sub(r'[^0-9]', '', barcode) if barcode else None
            
            # Verificar se já existe
            existing = session.query(OpenFoodFactsCache).filter(
                (OpenFoodFactsCache.food_name == normalized) |
                (OpenFoodFactsCache.barcode == barcode_clean if barcode_clean else False)
            ).first()
            
            now = datetime.utcnow()
            
            if existing:
                # Atualizar registro
                existing.product_name = nutrition_data.get('name', food_name)
                existing.brand = nutrition_data.get('brand', '')
                existing.calories = nutrition_data.get('calories', 0)
                existing.protein = nutrition_data.get('protein', 0)
                existing.fat_total = nutrition_data.get('fat_total', 0)
                existing.fat_saturated = nutrition_data.get('fat_saturated', 0)
                existing.carbs = nutrition_data.get('carbs', 0)
                existing.sugar = nutrition_data.get('sugar', 0)
                existing.fiber = nutrition_data.get('fiber', 0)
                existing.sodium = nutrition_data.get('sodium', 0)
                existing.potassium = nutrition_data.get('potassium', 0)
                existing.cholesterol = nutrition_data.get('cholesterol', 0)
                existing.nutrition_grade = nutrition_data.get('nutrition_grade', '')
                existing.serving_size = nutrition_data.get('serving_size', '100g')
                existing.image_url = nutrition_data.get('image_url', '')
                existing.accessed_at = now
                existing.hits += 1
            else:
                # Criar novo registro
                new_cache = OpenFoodFactsCache(
                    food_name=normalized,
                    barcode=barcode_clean,
                    product_name=nutrition_data.get('name', food_name),
                    brand=nutrition_data.get('brand', ''),
                    calories=nutrition_data.get('calories', 0),
                    protein=nutrition_data.get('protein', 0),
                    fat_total=nutrition_data.get('fat_total', 0),
                    fat_saturated=nutrition_data.get('fat_saturated', 0),
                    carbs=nutrition_data.get('carbs', 0),
                    sugar=nutrition_data.get('sugar', 0),
                    fiber=nutrition_data.get('fiber', 0),
                    sodium=nutrition_data.get('sodium', 0),
                    potassium=nutrition_data.get('potassium', 0),
                    cholesterol=nutrition_data.get('cholesterol', 0),
                    nutrition_grade=nutrition_data.get('nutrition_grade', ''),
                    serving_size=nutrition_data.get('serving_size', '100g'),
                    image_url=nutrition_data.get('image_url', ''),
                    cached_at=now,
                    accessed_at=now,
                    include_in_backup=True
                )
                session.add(new_cache)
            
            session.commit()
            return True
    
    except Exception as e:
        print(f"Erro ao salvar no cache OFF: {e}")
        return False


def cleanup_off_cache(days_inactive: int = 90) -> int:
    """
    Remove itens não acessados há X dias (LRU).
    
    🚧 NOVO: Limpeza inteligente
    - Remove automaticamente itens "frios" (90 dias sem acesso)
    - Libera espaço do banco
    - Não afeta backup (já foram salvos)
    - Recarrega automaticamente quando necessário
    
    Args:
        days_inactive: Número de dias sem acesso para remover (padrão: 90)
    
    Returns:
        Número de itens removidos
    """
    try:
        with get_db_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
            
            result = session.query(OpenFoodFactsCache).filter(
                OpenFoodFactsCache.accessed_at < cutoff_date
            ).delete()
            
            session.commit()
            
            if result > 0:
                print(f"🧹 Cache OFF: {result} itens removidos (não acessados há {days_inactive} dias)")
            
            return result
    
    except Exception as e:
        print(f"Erro ao limpar cache OFF: {e}")
        return 0


def get_off_cache_stats() -> Dict:
    """
    Retorna estatsticas do cache do Open Food Facts.
    
    📈 NOVO: Estatisticas detalhadas
    - Total de itens
    - Taxa de hit (acessos vs itens)
    - Produtos mais acessados
    - Tamanho estimado do banco
    
    Returns:
        Dict com estatsticas
    """
    try:
        with get_db_session() as session:
            total_items = session.query(func.count(OpenFoodFactsCache.id)).scalar()
            total_hits = session.query(func.sum(OpenFoodFactsCache.hits)).scalar() or 0
            
            # Top 10 itens mais acessados
            top_items = session.query(
                OpenFoodFactsCache.product_name,
                OpenFoodFactsCache.hits
            ).order_by(OpenFoodFactsCache.hits.desc()).limit(10).all()
            
            # Estimar tamanho (cada item ~1-2KB)
            estimated_size_mb = (total_items * 1.5) / 1024
            
            # Itens não acessados há 90 dias
            cutoff = datetime.utcnow() - timedelta(days=90)
            expired_items = session.query(func.count(OpenFoodFactsCache.id)).filter(
                OpenFoodFactsCache.accessed_at < cutoff
            ).scalar()
            
            return {
                'status': 'ready',
                'total_items': total_items,
                'total_hits': total_hits,
                'avg_hits_per_item': round(total_hits / max(total_items, 1), 2),
                'estimated_size_mb': round(estimated_size_mb, 2),
                'expired_items': expired_items,
                'top_items': [(item[0], item[1]) for item in top_items],
                'database': 'caloria.db',
                'include_in_backup': True,
                'cleanup_interval': '90 dias'
            }
    
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'database': 'caloria.db'
        }


def clear_off_cache() -> bool:
    """
    Limpa todo o cache do Open Food Facts.
    
    ⚠️ CUIDADO: Operação irreversível
    - Remove todos os itens em cache
    - Não afeta backup (já foram salvos)
    - Será recarregado conforme necessário
    
    Returns:
        True se limpou com sucesso
    """
    try:
        with get_db_session() as session:
            count = session.query(func.count(OpenFoodFactsCache.id)).scalar()
            session.query(OpenFoodFactsCache).delete()
            session.commit()
            print(f"🗑️ Cache OFF limpo: {count} itens removidos")
            return True
    
    except Exception as e:
        print(f"Erro ao limpar cache OFF: {e}")
        return False


def get_off_cache_size() -> str:
    """
    Retorna o tamanho estimado do cache em formato legível.
    
    Returns:
        String com tamanho (ex: "45 MB", "250 KB")
    """
    stats = get_off_cache_stats()
    if stats['status'] == 'ready':
        mb = stats['estimated_size_mb']
        if mb < 1:
            return f"{int(mb * 1024)} KB"
        return f"{mb:.1f} MB"
    return "N/A"


def should_cleanup_cache() -> bool:
    """
    Verifica se cache deve ser limpo (itens expirados > 10% do total).
    
    Returns:
        True se deve fazer limpeza
    """
    stats = get_off_cache_stats()
    if stats['status'] == 'ready':
        total = stats['total_items']
        expired = stats['expired_items']
        if total > 0 and (expired / total) > 0.1:  # 10% expirados
            return True
    return False


def auto_cleanup_if_needed() -> int:
    """
    Faz limpeza automática se necessário.
    Chamada automaticamente durante uso normal.
    
    Returns:
        Número de itens removidos (0 se não foi necessário)
    """
    if should_cleanup_cache():
        return cleanup_off_cache()
    return 0
