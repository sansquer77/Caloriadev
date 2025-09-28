from datetime import date, timedelta
from sqlalchemy import func
from db import Session, Meal, User

def save_meal(meal_data) -> None:
    """Salva registro do prato analisado no banco."""
    session = Session()
    meal = Meal(
        user_id=meal_data.user_id,
        date=meal_data.date,
        meal_type=meal_data.meal_type,
        calories=meal_data.calories,
        protein=meal_data.protein,
        fat=meal_data.fat,
        carbs=meal_data.carbs,
        sugar=meal_data.sugar
    )
    session.add(meal)
    session.commit()
    session.close()

def get_daily_macros(user_id: int, date_: date):
    """Retorna dados micro por dia somados."""
    session = Session()
    result = session.query(
        func.sum(Meal.calories),
        func.sum(Meal.protein),
        func.sum(Meal.fat),
        func.sum(Meal.carbs),
        func.sum(Meal.sugar)
    ).filter(
        Meal.user_id == user_id,
        Meal.date == date_
    ).one()
    session.close()
    return result

def get_aggregated_macros(user_id: int, start_date: date, end_date: date):
    """Agrega macros por período (semana ou mês)."""
    session = Session()
    result = session.query(
        func.sum(Meal.calories),
        func.sum(Meal.protein),
        func.sum(Meal.fat),
        func.sum(Meal.carbs),
        func.sum(Meal.sugar)
    ).filter(
        Meal.user_id == user_id,
        Meal.date >= start_date,
        Meal.date <= end_date
    ).one()
    session.close()
    return result

def create_user(username: str, password_hash: str, weight: float = None, height: float = None,
                cal_limit: float = None, protein_limit: float = None, fat_limit: float = None,
                carbs_limit: float = None, sugar_limit: float = None):
    """Cadastra um novo usuário no banco."""
    session = Session()
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
    session.close()
