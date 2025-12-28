from sqlalchemy import create_engine, Column, Integer, Float, Date, String, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
from datetime import datetime

# Configurar string de conexão via variável ambiente para segurança
# Suporta PostgreSQL (Digital Ocean) ou MySQL
DB_URL = os.getenv('DATABASE_URL', os.getenv('MYSQL_CONNECTION_STRING', 'sqlite:///caloria.db'))

# Digital Ocean usa 'postgres://' mas SQLAlchemy precisa de 'postgresql://'
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DB_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    weight = Column(Float, nullable=True)  # kg
    height = Column(Float, nullable=True)  # meters
    cal_limit = Column(Float, nullable=True)
    protein_limit = Column(Float, nullable=True)
    fat_limit = Column(Float, nullable=True)
    carbs_limit = Column(Float, nullable=True)
    sugar_limit = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    meals = relationship('Meal', back_populates='user')

class Meal(Base):
    __tablename__ = 'meals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    date = Column(Date, nullable=False)
    meal_type = Column(String(20), nullable=False)  # 'breakfast', 'lunch', 'dinner', 'snack'
    description = Column(Text, nullable=True)  # Descrição dos itens identificados
    
    # Macronutrientes principais
    calories = Column(Float, nullable=False, default=0)
    protein = Column(Float, nullable=False, default=0)
    carbs = Column(Float, nullable=False, default=0)
    sugar = Column(Float, nullable=False, default=0)
    fiber = Column(Float, nullable=True, default=0)
    
    # Gorduras detalhadas
    fat_total = Column(Float, nullable=False, default=0)
    fat_saturated = Column(Float, nullable=True, default=0)
    
    # Micronutrientes
    sodium = Column(Float, nullable=True, default=0)  # mg
    potassium = Column(Float, nullable=True, default=0)  # mg
    cholesterol = Column(Float, nullable=True, default=0)  # mg
    
    # Localização
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location_name = Column(String(255), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship('User', back_populates='meals')

def init_db():
    """Inicializa o banco de dados criando todas as tabelas."""
    Base.metadata.create_all(engine)

def get_session():
    """Retorna uma nova sessão do banco de dados."""
    return Session()
