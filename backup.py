"""
Módulo de Backup e Restore para o banco de dados MySQL.
Permite exportar e importar dados em formato JSON.
"""

import json
import os
from datetime import datetime, date
from typing import Optional, Dict, List
from db import get_session, User, Meal, init_db, DATABASE_URL, SQLITE_PATH
import subprocess
import shutil


class DateTimeEncoder(json.JSONEncoder):
    """Encoder customizado para serializar datetime e date."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return {'__datetime__': obj.isoformat()}
        if isinstance(obj, date):
            return {'__date__': obj.isoformat()}
        return super().default(obj)


def datetime_decoder(obj):
    """Decoder customizado para deserializar datetime e date."""
    if '__datetime__' in obj:
        return datetime.fromisoformat(obj['__datetime__'])
    if '__date__' in obj:
        return date.fromisoformat(obj['__date__'])
    return obj


def get_backup_folder() -> str:
    """Retorna o caminho da pasta de backups."""
    backup_folder = os.path.join(os.path.dirname(__file__), 'backups')
    if not os.path.exists(backup_folder):
        os.makedirs(backup_folder)
    return backup_folder


def export_to_json(filepath: Optional[str] = None) -> str:
    """
    Exporta todos os dados do banco para um arquivo JSON.
    
    Args:
        filepath: Caminho do arquivo de saída. Se None, gera automaticamente.
    
    Returns:
        Caminho do arquivo criado.
    """
    session = get_session()
    
    try:
        # Exportar usuários
        users = session.query(User).all()
        users_data = []
        for user in users:
            users_data.append({
                'id': user.id,
                'username': user.username,
                'password_hash': user.password_hash,
                'weight': user.weight,
                'height': user.height,
                'cal_limit': user.cal_limit,
                'protein_limit': user.protein_limit,
                'fat_limit': user.fat_limit,
                'carbs_limit': user.carbs_limit,
                'sugar_limit': user.sugar_limit,
                'created_at': user.created_at
            })
        
        # Exportar refeições
        meals = session.query(Meal).all()
        meals_data = []
        for meal in meals:
            meals_data.append({
                'id': meal.id,
                'user_id': meal.user_id,
                'date': meal.date,
                'meal_type': meal.meal_type,
                'description': meal.description,
                'calories': meal.calories,
                'protein': meal.protein,
                'carbs': meal.carbs,
                'sugar': meal.sugar,
                'fiber': meal.fiber,
                'fat_total': meal.fat_total,
                'fat_saturated': meal.fat_saturated,
                'sodium': meal.sodium,
                'potassium': meal.potassium,
                'cholesterol': meal.cholesterol,
                'latitude': meal.latitude,
                'longitude': meal.longitude,
                'location_name': meal.location_name,
                'created_at': meal.created_at
            })
        
        # Montar dados completos
        backup_data = {
            'backup_date': datetime.now(),
            'database_url': DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'local',  # Não expor credenciais
            'users': users_data,
            'meals': meals_data,
            'stats': {
                'total_users': len(users_data),
                'total_meals': len(meals_data)
            }
        }
        
        # Definir caminho do arquivo
        if not filepath:
            backup_folder = get_backup_folder()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filepath = os.path.join(backup_folder, f'backup_{timestamp}.json')
        
        # Salvar arquivo
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, cls=DateTimeEncoder, indent=2, ensure_ascii=False)
        
        return filepath
    
    finally:
        session.close()


def import_from_json(filepath: str, clear_existing: bool = False) -> Dict:
    """
    Importa dados de um arquivo JSON para o banco.
    
    Args:
        filepath: Caminho do arquivo JSON de backup.
        clear_existing: Se True, limpa dados existentes antes de importar.
    
    Returns:
        Dicionário com estatísticas da importação.
    """
    # Ler arquivo
    with open(filepath, 'r', encoding='utf-8') as f:
        backup_data = json.load(f, object_hook=datetime_decoder)
    
    session = get_session()
    
    try:
        stats = {
            'users_imported': 0,
            'meals_imported': 0,
            'users_skipped': 0,
            'meals_skipped': 0,
            'errors': []
        }
        
        # Limpar dados existentes se solicitado
        if clear_existing:
            session.query(Meal).delete()
            session.query(User).delete()
            session.commit()
        
        # Mapear IDs antigos para novos (caso já existam registros)
        user_id_map = {}
        
        # Importar usuários
        for user_data in backup_data.get('users', []):
            try:
                # Verificar se usuário já existe
                existing = session.query(User).filter(User.username == user_data['username']).first()
                
                if existing:
                    user_id_map[user_data['id']] = existing.id
                    stats['users_skipped'] += 1
                else:
                    user = User(
                        username=user_data['username'],
                        password_hash=user_data['password_hash'],
                        weight=user_data.get('weight'),
                        height=user_data.get('height'),
                        cal_limit=user_data.get('cal_limit'),
                        protein_limit=user_data.get('protein_limit'),
                        fat_limit=user_data.get('fat_limit'),
                        carbs_limit=user_data.get('carbs_limit'),
                        sugar_limit=user_data.get('sugar_limit'),
                        created_at=user_data.get('created_at', datetime.now())
                    )
                    session.add(user)
                    session.flush()  # Para obter o ID
                    user_id_map[user_data['id']] = user.id
                    stats['users_imported'] += 1
            except Exception as e:
                stats['errors'].append(f"Erro ao importar usuário {user_data.get('username')}: {str(e)}")
        
        # Importar refeições
        for meal_data in backup_data.get('meals', []):
            try:
                # Mapear user_id
                old_user_id = meal_data['user_id']
                new_user_id = user_id_map.get(old_user_id)
                
                if not new_user_id:
                    stats['meals_skipped'] += 1
                    continue
                
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
                    latitude=meal_data.get('latitude'),
                    longitude=meal_data.get('longitude'),
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
