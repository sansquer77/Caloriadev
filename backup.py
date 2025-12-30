"""
Utilities de Backup / Restore

Fornece operações simples sobre o arquivo SQLite usado em desenvolvimento
(.db) e suporte básico para arquivos JSON de backup gerados anteriormente.

Funções expostas:
- `quick_backup()` : copia o arquivo SQLite atual para a pasta `backups/` e retorna o caminho
- `list_backups()` : lista arquivos em `backups/` com metadados
- `delete_backup(filepath)` : remove o arquivo especificado
- `import_from_json(filepath, clear_existing=False)` : restaura um arquivo `.db` substituindo o DB atual, ou importa JSON
"""

import os
import shutil
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from db import SQLITE_PATH, get_session, User, Meal


def get_backup_folder() -> str:
    folder = os.path.join(os.path.dirname(__file__), 'backups')
    os.makedirs(folder, exist_ok=True)
    return folder


def _sqlite_counts(db_path: str) -> Dict[str, int]:
    counts = {'total_users': 0, 'total_meals': 0}
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM users")
        counts['total_users'] = cur.fetchone()[0] if cur.fetchone() is not None else 0
    except Exception:
        # Try again more safely
        try:
            cur.execute("SELECT count(*) FROM users")
            counts['total_users'] = cur.fetchone()[0]
        except Exception:
            counts['total_users'] = 0
    try:
        cur.execute("SELECT count(*) FROM meals")
        counts['total_meals'] = cur.fetchone()[0] if cur.fetchone() is not None else 0
    except Exception:
        counts['total_meals'] = 0
    try:
        conn.close()
    except Exception:
        pass
    return counts


def quick_backup() -> str:
    """Copia o arquivo SQLite atual para `backups/` e retorna o caminho criado."""
    if not SQLITE_PATH or not os.path.exists(SQLITE_PATH):
        raise FileNotFoundError(f"Arquivo de banco de dados não encontrado: {SQLITE_PATH}")

    backup_folder = get_backup_folder()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(backup_folder, f'caloria_backup_{timestamp}.db')
    shutil.copy2(SQLITE_PATH, dest)
    return dest


def list_backups() -> List[Dict]:
    """Lista arquivos na pasta `backups/` com metadados usados pela UI."""
    folder = get_backup_folder()
    files = sorted([os.path.join(folder, f) for f in os.listdir(folder)], key=os.path.getmtime, reverse=True)
    out = []
    for f in files:
        try:
            stat = os.path.getmtime(f)
            created = datetime.fromtimestamp(stat)
            size_mb = round(os.path.getsize(f) / (1024 * 1024), 2)
            filename = os.path.basename(f)
            counts = {'total_users': None, 'total_meals': None}
            if f.lower().endswith('.db'):
                # Try to open sqlite and count
                try:
                    conn = sqlite3.connect(f)
                    cur = conn.cursor()
                    cur.execute("SELECT count(*) FROM users")
                    counts['total_users'] = cur.fetchone()[0]
                    cur.execute("SELECT count(*) FROM meals")
                    counts['total_meals'] = cur.fetchone()[0]
                    conn.close()
                except Exception:
                    counts = {'total_users': 0, 'total_meals': 0}
            else:
                # If JSON, try to read stats
                if f.lower().endswith('.json'):
                    try:
                        with open(f, 'r', encoding='utf-8') as fh:
                            data = json.load(fh)
                            stats = data.get('stats', {})
                            counts['total_users'] = stats.get('total_users')
                            counts['total_meals'] = stats.get('total_meals')
                    except Exception:
                        counts = {'total_users': 0, 'total_meals': 0}

            out.append({
                'filename': filename,
                'filepath': f,
                'created': created,
                'size_mb': size_mb,
                'total_users': counts.get('total_users'),
                'total_meals': counts.get('total_meals')
            })
        except Exception:
            continue

    return out


def delete_backup(filepath: str) -> bool:
    if not os.path.exists(filepath):
        return False
    os.remove(filepath)
    return True


def import_from_json(filepath: str, clear_existing: bool = False) -> Dict:
    """Restaura um backup.

    - Se `filepath` terminar em `.db`, substitui o arquivo SQLite atual pelo backup (faz backup prévio do DB atual).
    - Se `filepath` terminar em `.json`, tenta importar usuários e refeições do JSON.
    """
    if filepath.lower().endswith('.db'):
        # Backup atual antes de sobrescrever
        if os.path.exists(SQLITE_PATH):
            pre_backup = os.path.join(get_backup_folder(), f'pre_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
            shutil.copy2(SQLITE_PATH, pre_backup)
        else:
            pre_backup = None

        shutil.copy2(filepath, SQLITE_PATH)
        return {'restored': True, 'from': filepath, 'backup_before_restore': pre_backup}

    # JSON import fallback
    if filepath.lower().endswith('.json'):
        with open(filepath, 'r', encoding='utf-8') as fh:
            data = json.load(fh)

        session = get_session()
        stats = {'users_imported': 0, 'meals_imported': 0, 'users_skipped': 0, 'meals_skipped': 0}
        try:
            if clear_existing:
                session.query(Meal).delete()
                session.query(User).delete()
                session.commit()

            user_map = {}
            for u in data.get('users', []):
                username = u.get('username')
                if not username:
                    continue
                existing = session.query(User).filter(User.username == username).first()
                if existing:
                    user_map[u.get('id')] = existing.id
                    stats['users_skipped'] += 1
                    continue

                user = User(
                    username=username,
                    hashed_password=u.get('password_hash'),
                    peso_kg=u.get('weight'),
                    altura_cm=int(u.get('height') * 100) if u.get('height') else None,
                    calorias_diarias=u.get('cal_limit'),
                    proteina_pct=u.get('protein_limit'),
                    gordura_pct=u.get('fat_limit'),
                    carboidrato_pct=u.get('carbs_limit')
                )
                session.add(user)
                session.flush()
                user_map[u.get('id')] = user.id
                stats['users_imported'] += 1

            for m in data.get('meals', []):
                old_uid = m.get('user_id')
                new_uid = user_map.get(old_uid)
                if not new_uid:
                    stats['meals_skipped'] += 1
                    continue
                meal = Meal(
                    user_id=new_uid,
                    date=m.get('date'),
                    meal_type=m.get('meal_type'),
                    description=m.get('description'),
                    calories=m.get('calories') or 0,
                    protein=m.get('protein') or 0,
                    carbs=m.get('carbs') or 0,
                    fat_total=m.get('fat_total') or 0,
                    sugar=m.get('sugar') or 0,
                    fiber=m.get('fiber') or 0,
                    location_name=m.get('location_name')
                )
                session.add(meal)
                stats['meals_imported'] += 1

            session.commit()
            return stats
        finally:
            session.close()

    raise ValueError("Formato de backup não suportado. Use .db ou .json")

                meal = Meal(
                    user_id=new_user_id,
                    date=meal_data['date'],
                    meal_type=meal_data['meal_type'],
                    description=meal_data.get('description'),
                    calories=meal_data.get('calories', 0),
                    protein=meal_data.get('protein', 0),
                    carbs=meal_data.get('carbs', 0),
                    sugar=meal_data.get('sugar', 0),
                    fiber=meal_data.get('fiber', 0),
                    fat_total=meal_data.get('fat_total', 0),
                    fat_saturated=meal_data.get('fat_saturated', 0),
                    sodium=meal_data.get('sodium', 0),
                    potassium=meal_data.get('potassium', 0),
                    cholesterol=meal_data.get('cholesterol', 0),
                    # latitude/longitude removed from schema
                    location_name=meal_data.get('location_name'),
                    created_at=meal_data.get('created_at', datetime.now())
                )
                session.add(meal)
                stats['meals_imported'] += 1
            except Exception as e:
                stats['errors'].append(f"Erro ao importar refeição: {str(e)}")
        
        session.commit()
        return stats
    
    except Exception as e:
        session.rollback()
        raise e
    
    finally:
        session.close()


def list_backups() -> List[Dict]:
    """
    Lista todos os backups disponíveis.
    
    Returns:
        Lista de dicionários com informações dos backups.
    """
    backup_folder = get_backup_folder()
    backups = []
    
    for filename in os.listdir(backup_folder):
        if filename.endswith('.json'):
            filepath = os.path.join(backup_folder, filename)
            stat = os.stat(filepath)
            
            # Tentar ler metadados do backup
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f, object_hook=datetime_decoder)
                    stats = data.get('stats', {})
            except:
                stats = {}
            
            backups.append({
                'filename': filename,
                'filepath': filepath,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created': datetime.fromtimestamp(stat.st_ctime),
                'total_users': stats.get('total_users', 'N/A'),
                'total_meals': stats.get('total_meals', 'N/A')
            })
    
    # Ordenar por data de criação (mais recente primeiro)
    backups.sort(key=lambda x: x['created'], reverse=True)
    return backups


def delete_backup(filepath: str) -> bool:
    """
    Remove um arquivo de backup.
    
    Args:
        filepath: Caminho do arquivo a ser removido.
    
    Returns:
        True se removido com sucesso, False caso contrário.
    """
    try:
        if os.path.exists(filepath) and filepath.endswith('.json'):
            os.remove(filepath)
            return True
        return False
    except Exception:
        return False


def mysql_dump(output_file: Optional[str] = None) -> Optional[str]:
    """
    Faz backup usando mysqldump (requer MySQL instalado).
    
    Args:
        output_file: Caminho do arquivo de saída.
    
    Returns:
        Caminho do arquivo criado ou None em caso de erro.
    """
    # Extrair configurações da URL
    if 'mysql' not in DATABASE_URL:
        return None
    
    try:
        # Parse da URL: mysql+pymysql://user:pass@host:port/database
        import re
        pattern = r'mysql\+pymysql://([^:]+):([^@]*)@([^:]+):(\d+)/([^?]+)'
        match = re.match(pattern, DATABASE_URL)
        
        if not match:
            return None
        
        user, password, host, port, database = match.groups()
        
        # Definir arquivo de saída
        if not output_file:
            backup_folder = get_backup_folder()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(backup_folder, f'mysqldump_{timestamp}.sql')
        
        # Montar comando
        cmd = ['mysqldump', '-h', host, '-P', port, '-u', user]
        if password:
            cmd.extend([f'-p{password}'])
        cmd.append(database)
        
        # Executar
        with open(output_file, 'w') as f:
            subprocess.run(cmd, stdout=f, check=True)
        
        return output_file
    
    except Exception as e:
        print(f"Erro ao executar mysqldump: {e}")
        return None


def mysql_restore(sql_file: str) -> bool:
    """
    Restaura backup usando mysql (requer MySQL instalado).
    
    Args:
        sql_file: Caminho do arquivo SQL.
    
    Returns:
        True se restaurado com sucesso.
    """
    if 'mysql' not in DATABASE_URL:
        return False
    
    try:
        import re
        pattern = r'mysql\+pymysql://([^:]+):([^@]*)@([^:]+):(\d+)/([^?]+)'
        match = re.match(pattern, DATABASE_URL)
        
        if not match:
            return False
        
        user, password, host, port, database = match.groups()
        
        # Montar comando
        cmd = ['mysql', '-h', host, '-P', port, '-u', user]
        if password:
            cmd.extend([f'-p{password}'])
        cmd.append(database)
        
        # Executar
        with open(sql_file, 'r') as f:
            subprocess.run(cmd, stdin=f, check=True)
        
        return True
    
    except Exception as e:
        print(f"Erro ao restaurar: {e}")
        return False


# Funções de conveniência
def quick_backup() -> str:
    """Faz um backup rápido e retorna o caminho do arquivo."""
    return export_to_json()


def quick_restore(backup_index: int = 0) -> Dict:
    """
    Restaura o backup mais recente (ou pelo índice).
    
    Args:
        backup_index: Índice do backup (0 = mais recente).
    
    Returns:
        Estatísticas da restauração.
    """
    backups = list_backups()
    if not backups or backup_index >= len(backups):
        raise ValueError("Backup não encontrado")
    
    return import_from_json(backups[backup_index]['filepath'])
