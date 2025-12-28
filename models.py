from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List

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
    fat_total: float
    fat_saturated: float
    carbs: float
    sugar: float
    fiber: float = 0.0
    sodium: float = 0.0
    potassium: float = 0.0
    cholesterol: float = 0.0
    description: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    items_detected: List[str] = field(default_factory=list)

@dataclass
class LocationData:
    latitude: float
    longitude: float
    name: str = ""
    address: str = ""
