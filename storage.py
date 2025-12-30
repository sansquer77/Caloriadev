"""
Módulo de armazenamento - funções de persistência de dados.

Este módulo gerencia todas as operações CRUD com o banco de dados,
incluindo refeições, usuários e agregações de macronutrientes.
"""
from datetime import date, timedelta, datetime
from sqlalchemy import func, and_
from db import Session, Meal, User, get_session, get_db_session
from typing import Optional, List, Dict, Tuple

def save_meal(meal_data) -> int:
    """
    Salva registro do prato analisado no banco e retorna o ID.
    
    Args:
        meal_data: Objeto com dados da refeição (MealData ou similar)
        
    Returns:
        ID da refeição salva
    """
    with get_db_session() as session:
        meal = Meal(
            user_id=meal_data.user_id,
            date=meal_data.date,
            meal_type=meal_data.meal_type,
            description=getattr(meal_data, 'description', ''),
            calories=meal_data.calories,
            protein=meal_data.protein,
            carbs=meal_data.carbs,
            sugar=meal_data.sugar,
            fiber=getattr(meal_data, 'fiber', 0),
            fat_total=meal_data.fat_total,
            fat_saturated=getattr(meal_data, 'fat_saturated', 0),
            sodium=getattr(meal_data, 'sodium', 0),
            potassium=getattr(meal_data, 'potassium', 0),
            cholesterol=getattr(meal_data, 'cholesterol', 0),
            # latitude/longitude removed from schema; keep only location_name
            location_name=getattr(meal_data, 'location_name', None),
            created_at=getattr(meal_data, 'created_at', datetime.now())
        )
        session.add(meal)
        session.commit()
        return meal.id

def get_daily_macros(user_id: int, date_: date) -> Dict[str, float]:
    """Retorna dados macro por dia somados."""
    with get_db_session() as session:
        result = session.query(
            func.sum(Meal.calories).label('calories'),
            func.sum(Meal.protein).label('protein'),
            func.sum(Meal.fat_total).label('fat_total'),
            func.sum(Meal.fat_saturated).label('fat_saturated'),
            func.sum(Meal.carbs).label('carbs'),
            func.sum(Meal.sugar).label('sugar'),
            func.sum(Meal.sodium).label('sodium'),
            func.sum(Meal.fiber).label('fiber')
        ).filter(
            Meal.user_id == user_id,
            Meal.date == date_
        ).one()
        
        return {
            'calories': result.calories or 0,
            'protein': result.protein or 0,
            'fat_total': result.fat_total or 0,
            'fat_saturated': result.fat_saturated or 0,
            'carbs': result.carbs or 0,
            'sugar': result.sugar or 0,
            'fiber': result.fiber or 0,
            'sodium': result.sodium or 0
        }

def get_aggregated_macros(user_id: int, start_date: date, end_date: date) -> Dict[str, float]:
    """Agrega macros por período (semana ou mês)."""
    with get_db_session() as session:
        result = session.query(
            func.sum(Meal.calories).label('calories'),
            func.sum(Meal.protein).label('protein'),
            func.sum(Meal.fat_total).label('fat_total'),
            func.sum(Meal.fat_saturated).label('fat_saturated'),
            func.sum(Meal.carbs).label('carbs'),
            func.sum(Meal.sugar).label('sugar'),
            func.sum(Meal.fiber).label('fiber'),
            func.sum(Meal.sodium).label('sodium')
        ).filter(
            Meal.user_id == user_id,
            Meal.date >= start_date,
            Meal.date <= end_date
        ).one()
        
        return {
            'calories': result.calories or 0,
            'protein': result.protein or 0,
            'fat_total': result.fat_total or 0,
            'fat_saturated': result.fat_saturated or 0,
            'carbs': result.carbs or 0,
            'sugar': result.sugar or 0,
            'fiber': result.fiber or 0,
            'sodium': result.sodium or 0
        }

def get_meals_with_location(user_id: int, start_date: date = None, end_date: date = None) -> List[Dict]:
    """Retorna refeições com nome de local (sem coordenadas)."""
    with get_db_session() as session:
        query = session.query(Meal).filter(
            Meal.user_id == user_id,
            Meal.location_name.isnot(None)
        )

        if start_date:
            query = query.filter(Meal.date >= start_date)
        if end_date:
            query = query.filter(Meal.date <= end_date)

        meals = query.order_by(Meal.created_at.desc()).all()

        return [{
            'id': meal.id,
            'date': meal.date if isinstance(meal.date, date) else datetime.strptime(str(meal.date), '%Y-%m-%d').date() if meal.date else None,
            'meal_type': meal.meal_type,
            'description': meal.description,
            'calories': meal.calories,
            'protein': meal.protein,
            'carbs': meal.carbs,
            'fat_total': meal.fat_total,
            'sugar': meal.sugar,
            'fiber': meal.fiber,
            'sodium': meal.sodium,
            'location_name': meal.location_name,
            'created_at': meal.created_at
        } for meal in meals]

def get_user_meals(user_id: int, limit: int = 50) -> List[Dict]:
    """Retorna as últimas refeições do usuário."""
    with get_db_session() as session:
        meals = session.query(Meal).filter(
            Meal.user_id == user_id
        ).order_by(Meal.created_at.desc()).limit(limit).all()
        
        return [{
            'id': meal.id,
            'date': meal.date if isinstance(meal.date, date) else datetime.strptime(str(meal.date), '%Y-%m-%d').date() if meal.date else None,
            'meal_type': meal.meal_type,
            'description': meal.description,
            'calories': meal.calories,
            'protein': meal.protein,
            'carbs': meal.carbs,
            'fat_total': meal.fat_total,
            'fat_saturated': meal.fat_saturated,
            'sugar': meal.sugar,
            'fiber': meal.fiber,
            'location_name': meal.location_name,
            'created_at': meal.created_at
        } for meal in meals]

def create_user(username: str, password_hash: str, weight: float = None, height: float = None,
                cal_limit: float = None, protein_limit: float = None, fat_limit: float = None,
                carbs_limit: float = None, sugar_limit: float = None, birth_date = None,
                protein_pct: float = None, fat_pct: float = None, carbs_pct: float = None,
                email: str = None) -> int:
    """Cadastra um novo usuário no banco e retorna o ID.

    Faz o mapeamento entre os nomes de campo usados pela UI e os nomes
    das colunas do modelo `User`.
    """
    with get_db_session() as session:
        user = User(
            username=username,
            email=email,
            hashed_password=password_hash,
            peso_kg=weight if weight is not None else None,
            altura_cm=int(height * 100) if height is not None else None,
            data_nascimento=birth_date,
            calorias_diarias=cal_limit,
            proteina_pct=protein_pct or 30.0,
            gordura_pct=fat_pct or 25.0,
            carboidrato_pct=carbs_pct or 45.0
        )
        session.add(user)
        session.commit()
        return user.id

def get_user_by_username(username: str) -> Optional[Dict]:
    """Busca usuário por username."""
    with get_db_session() as session:
        user = session.query(User).filter(User.username == username).first()
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'password_hash': user.hashed_password,
                'weight': user.peso_kg,
                'height': (user.altura_cm / 100.0) if user.altura_cm else None,
                'cal_limit': user.calorias_diarias,
                'protein_limit': None,
                'fat_limit': None,
                'carbs_limit': None,
                'sugar_limit': None
            }
        return None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Busca usuário por ID."""
    with get_db_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'weight': user.peso_kg,
                'height': (user.altura_cm / 100.0) if user.altura_cm else None,
                'birth_date': user.data_nascimento,
                'cal_limit': user.calorias_diarias,
                'protein_limit': None,
                'fat_limit': None,
                'carbs_limit': None,
                'sugar_limit': None,
                'protein_pct': user.proteina_pct or 30.0,
                'fat_pct': user.gordura_pct or 25.0,
                'carbs_pct': user.carboidrato_pct or 45.0
            }
        return None

def update_user_profile(user_id: int, **kwargs) -> bool:
    """Atualiza o perfil do usuário."""
    with get_db_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            # Map keys from UI-friendly names to model attribute names
            for key, value in kwargs.items():
                if key == 'weight':
                    user.peso_kg = value
                elif key == 'height':
                    user.altura_cm = int(value * 100) if value is not None else None
                elif key == 'carbs_pct':
                    user.carboidrato_pct = float(value)
                elif key == 'protein_pct':
                    user.proteina_pct = float(value)
                elif key == 'fat_pct':
                    user.gordura_pct = float(value)
                elif hasattr(user, key):
                    setattr(user, key, value)
            session.commit()
            return True
        return False

def update_user_password(user_id: int, new_password_hash: str) -> bool:
    """Atualiza a senha do usuário."""
    with get_db_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            user.hashed_password = new_password_hash
            session.commit()
            return True
        return False

def delete_meal(meal_id: int, user_id: int) -> bool:
    """Remove uma refeição do histórico."""
    with get_db_session() as session:
        meal = session.query(Meal).filter(
            Meal.id == meal_id,
            Meal.user_id == user_id
        ).first()
        if meal:
            session.delete(meal)
            session.commit()
            return True
        return False
