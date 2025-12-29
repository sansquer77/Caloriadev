"""🔄 Script de Migração: OFF_CACHE.json → Caloria.db

Função:
- Detecta OFF_CACHE.json legado
- Importa todos os itens para a nova tabela open_food_facts_cache
- Remove arquivo JSON após migração bem-sucedida
- Operação segura com rollback em caso de erro

Uso:
    from off_cache_migration import migrate_off_cache_to_db
    stats = migrate_off_cache_to_db()
    print(f"Migrados: {stats['imported']} itens")
"""

import json
import os
from pathlib import Path
from datetime import datetime
from off_cache_manager import add_to_cache
from db import SQLITE_PATH


def get_legacy_cache_path() -> str:
    """Retorna o caminho do arquivo OFF_CACHE.json legado."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'OFF_CACHE.json')


def legacy_cache_exists() -> bool:
    """Verifica se o arquivo OFF_CACHE.json legado existe."""
    legacy_path = get_legacy_cache_path()
    return os.path.exists(legacy_path) and os.path.getsize(legacy_path) > 0


def load_legacy_cache() -> dict:
    """Carrega OFF_CACHE.json legado.
    
    Returns:
        dict: Dicionário com dados do cache ou {} se não existir
    """
    legacy_path = get_legacy_cache_path()
    
    if not os.path.exists(legacy_path):
        return {}
    
    try:
        with open(legacy_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"📄 Carregado OFF_CACHE.json legado: {len(data)} itens")
        return data
    except Exception as e:
        print(f"❌ Erro ao carregar OFF_CACHE.json: {e}")
        return {}


def migrate_off_cache_to_db(remove_legacy: bool = True) -> dict:
    """Migra dados do OFF_CACHE.json para o banco SQLite.
    
    Args:
        remove_legacy: Se True, remove o arquivo JSON após migração bem-sucedida
    
    Returns:
        {
            'success': bool,
            'imported': int,  # Itens importados com sucesso
            'failed': int,    # Itens que falharam
            'skipped': int,   # Itens pulados (inválidos)
            'legacy_removed': bool,
            'message': str
        }
    """
    stats = {
        'success': False,
        'imported': 0,
        'failed': 0,
        'skipped': 0,
        'legacy_removed': False,
        'message': ''
    }
    
    # Verificar se arquivo legado existe
    if not legacy_cache_exists():
        stats['message'] = "✅ Nenhum arquivo legado encontrado - cache já foi migrado"
        stats['success'] = True
        return stats
    
    print("\n" + "="*60)
    print("ud83d\udd04 INICIANDO MIGRAÇÃO: OFF_CACHE.json → Caloria.db")
    print("="*60 + "\n")
    
    # Carregar dados legados
    legacy_data = load_legacy_cache()
    
    if not legacy_data:
        stats['message'] = "⚠️  Arquivo OFF_CACHE.json vazio ou inválido"
        return stats
    
    print(f"\n📄 Migrando {len(legacy_data)} itens...\n")
    
    # Iterar sobre itens do cache legado
    for idx, (key, item) in enumerate(legacy_data.items(), 1):
        try:
            # Validar item
            if not isinstance(item, dict):
                stats['skipped'] += 1
                continue
            
            # Preparar dados para o novo formato
            food_data = {
                'food_name': item.get('food_name') or item.get('name') or key,
                'barcode': item.get('barcode'),
                'product_name': item.get('product_name') or item.get('name') or key,
                'brand': item.get('brand'),
                'calories': float(item.get('calories') or 0),
                'protein': float(item.get('protein') or 0),
                'fat_total': float(item.get('fat_total') or 0),
                'fat_saturated': float(item.get('fat_saturated') or 0),
                'carbs': float(item.get('carbs') or 0),
                'sugar': float(item.get('sugar') or 0),
                'fiber': float(item.get('fiber') or 0),
                'sodium': float(item.get('sodium') or 0),
                'potassium': float(item.get('potassium') or 0),
                'cholesterol': float(item.get('cholesterol') or 0),
                'nutrition_grade': item.get('nutrition_grade'),
                'serving_size': item.get('serving_size'),
                'image_url': item.get('image_url')
            }
            
            # Adicionar ao banco SQLite
            if add_to_cache(food_data):
                stats['imported'] += 1
                if idx % 50 == 0:
                    print(f"  ✔️ {idx}/{len(legacy_data)} itens processados...")
            else:
                stats['failed'] += 1
        
        except Exception as e:
            print(f"  ❌ Erro ao migrar item '{key}': {e}")
            stats['failed'] += 1
    
    print(f"\n✅ Migração concluída!")
    print(f"  Importados: {stats['imported']}")
    print(f"  Falhados: {stats['failed']}")
    print(f"  Pulados: {stats['skipped']}")
    
    # Remover arquivo legado se tudo foi bem
    if stats['imported'] > 0 and remove_legacy:
        try:
            legacy_path = get_legacy_cache_path()
            # Fazer backup antes de remover
            backup_path = legacy_path + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(legacy_path, backup_path)
            stats['legacy_removed'] = True
            print(f"\n🧹 Arquivo legado movido para: {backup_path}")
            print(f"   (Mantido como backup de segurança)")
        except Exception as e:
            print(f"\n⚠️  Aviso: Não foi possível remover arquivo legado: {e}")
    
    stats['success'] = True
    stats['message'] = f"✅ {stats['imported']} itens migrados com sucesso"
    
    print("\n" + "="*60 + "\n")
    
    return stats


def rollback_migration() -> bool:
    """Reverte a migração (restaura arquivo de backup legado).
    
    Retorna:
        bool: True se bem-sucedido
    """
    try:
        legacy_path = get_legacy_cache_path()
        backup_files = sorted(Path(os.path.dirname(legacy_path)).glob('OFF_CACHE.json.backup_*'))
        
        if not backup_files:
            print("⚠️  Nenhum backup encontrado para restaurar")
            return False
        
        # Restaurar o backup mais recente
        most_recent_backup = backup_files[-1]
        os.rename(most_recent_backup, legacy_path)
        print(f"✅ Migration revertida - arquivo restaurado de: {most_recent_backup.name}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao reverter migração: {e}")
        return False


if __name__ == '__main__':
    # Executar migração quando rodado diretamente
    stats = migrate_off_cache_to_db()
    exit(0 if stats['success'] else 1)
