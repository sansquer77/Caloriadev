"""
Módulo de modelos de dados - dataclasses para transferência de dados.

Define estruturas imutáveis para representar usuários, refeições e localizações,
garantindo tipagem e validação de dados.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List


@dataclass
class UserData:
    """Dados do usuário para transferência entre camadas."""
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
    """Dados de uma refeição para registro no banco."""
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
    location_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    items_detected: List[str] = field(default_factory=list)


@dataclass
class LocationData:
    """Dados de geolocalização de uma refeição."""
    latitude: float
    longitude: float
    name: str = ""
    address: str = ""
