from datetime import date, timedelta, datetime
from sqlalchemy import func, and_
from db import Session, Meal, User, get_session
from typing import Optional, List, Dict, Tuple

def save_meal(meal_data) -> int:
    """Salva registro do prato analisado no banco e retorna o ID."""
    session = get_session()
    try:
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
            latitude=getattr(meal_data, 'latitude', None),
            longitude=getattr(meal_data, 'longitude', None),
            location_name=getattr(meal_data, 'location_name', None),
            created_at=getattr(meal_data, 'created_at', datetime.now())
        )
        session.add(meal)
        session.commit()
        meal_id = meal.id
        return meal_id
    finally:
        session.close()

def get_daily_macros(user_id: int, date_: date) -> Dict[str, float]:
    """Retorna dados macro por dia somados."""
    session = get_session()
    try:
        result = session.query(
            func.sum(Meal.calories).label('calories'),
            func.sum(Meal.protein).label('protein'),
            func.sum(Meal.fat_total).label('fat_total'),
            func.sum(Meal.fat_saturated).label('fat_saturated'),
            func.sum(Meal.carbs).label('carbs'),
            func.sum(Meal.sugar).label('sugar'),
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
            'fiber': result.fiber or 0
        }
    finally:
        session.close()

def get_aggregated_macros(user_id: int, start_date: date, end_date: date) -> Dict[str, float]:
    """Agrega macros por período (semana ou mês)."""
    session = get_session()
    try:
        result = session.query(
            func.sum(Meal.calories).label('calories'),
            func.sum(Meal.protein).label('protein'),
            func.sum(Meal.fat_total).label('fat_total'),
            func.sum(Meal.fat_saturated).label('fat_saturated'),
            func.sum(Meal.carbs).label('carbs'),
            func.sum(Meal.sugar).label('sugar'),
            func.sum(Meal.fiber).label('fiber')
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
            'fiber': result.fiber or 0
        }
    finally:
        session.close()

def get_meals_with_location(user_id: int, start_date: date = None, end_date: date = None) -> List[Dict]:
    """Retorna refeições com dados de localização para exibição em mapa."""
    session = get_session()
    try:
        query = session.query(Meal).filter(
            Meal.user_id == user_id,
            Meal.latitude.isnot(None),
            Meal.longitude.isnot(None)
        )
        
        if start_date:
            query = query.filter(Meal.date >= start_date)
        if end_date:
            query = query.filter(Meal.date <= end_date)
        
        meals = query.order_by(Meal.created_at.desc()).all()
        
        return [{
            'id': meal.id,
            'date': meal.date,
            'meal_type': meal.meal_type,
            'description': meal.description,
            'calories': meal.calories,
            'protein': meal.protein,
            'carbs': meal.carbs,
            'fat_total': meal.fat_total,
            'sugar': meal.sugar,
            'latitude': meal.latitude,
            'longitude': meal.longitude,
            'location_name': meal.location_name,
            'created_at': meal.created_at
        } for meal in meals]
    finally:
        session.close()

def get_user_meals(user_id: int, limit: int = 50) -> List[Dict]:
    """Retorna as últimas refeições do usuário."""
    session = get_session()
    try:
        meals = session.query(Meal).filter(
            Meal.user_id == user_id
        ).order_by(Meal.created_at.desc()).limit(limit).all()
        
        return [{
            'id': meal.id,
            'date': meal.date,
            'meal_type': meal.meal_type,
            'description': meal.description,
            'calories': meal.calories,
            'protein': meal.protein,
            'carbs': meal.carbs,
            'fat_total': meal.fat_total,
            'fat_saturated': meal.fat_saturated,
            'sugar': meal.sugar,
            'fiber': meal.fiber,
            'latitude': meal.latitude,
            'longitude': meal.longitude,
            'location_name': meal.location_name,
            'created_at': meal.created_at
        } for meal in meals]
    finally:
        session.close()

def create_user(username: str, password_hash: str, weight: float = None, height: float = None,
                cal_limit: float = None, protein_limit: float = None, fat_limit: float = None,
                carbs_limit: float = None, sugar_limit: float = None) -> int:
    """Cadastra um novo usuário no banco e retorna o ID."""
    session = get_session()
    try:
        user = User(
            username=username,
            password_hash=password_hash,
            weight=weight,
            height=height,
            cal_limit=cal_limit,
            protein_limit=protein_limit,
            fat_limit=fat_limit,
            carbs_limit=carbs_limit,
            sugar_limit=sugar_limit
        )
        session.add(user)
        session.commit()
        user_id = user.id
        return user_id
    finally:
        session.close()

def get_user_by_username(username: str) -> Optional[Dict]:
    """Busca usuário por username."""
    session = get_session()
    try:
        user = session.query(User).filter(User.username == username).first()
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'password_hash': user.password_hash,
                'weight': user.weight,
                'height': user.height,
                'cal_limit': user.cal_limit,
                'protein_limit': user.protein_limit,
                'fat_limit': user.fat_limit,
                'carbs_limit': user.carbs_limit,
                'sugar_limit': user.sugar_limit
            }
        return None
    finally:
        session.close()

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Busca usuário por ID."""
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if user:
            return {
                'id': user.id,
                'username': user.username,
                'weight': user.weight,
                'height': user.height,
                'cal_limit': user.cal_limit,
                'protein_limit': user.protein_limit,
                'fat_limit': user.fat_limit,
                'carbs_limit': user.carbs_limit,
                'sugar_limit': user.sugar_limit
            }
        return None
    finally:
        session.close()

def delete_meal(meal_id: int, user_id: int) -> bool:
    """Remove uma refeição do histórico."""
    session = get_session()
    try:
        meal = session.query(Meal).filter(
            Meal.id == meal_id,
            Meal.user_id == user_id
        ).first()
        if meal:
            session.delete(meal)
            session.commit()
            return True
        return False
    finally:
        session.close()
