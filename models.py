from dataclasses import dataclass
from datetime import date

@dataclass
class UserData:
    username: str
    weight: float
    height: float
    cal_limit: float
    protein_limit: float
    fat_limit: float
    carbs_limit: float
    sugar_limit: float

@dataclass
class MealData:
    user_id: int
    date: date
    meal_type: str
    calories: float
    protein: float
    fat: float
    carbs: float
    sugar: float
