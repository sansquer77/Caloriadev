from sqlalchemy import create_engine, Column, Integer, Float, Date, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os

# Configurar string de conexão via variável ambiente para segurança
DB_URL = os.getenv('MYSQL_CONNECTION_STRING', 'mysql+pymysql://user:password@localhost/dbname')

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

    meals = relationship('Meal', back_populates='user')

class Meal(Base):
    __tablename__ = 'meals'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    date = Column(Date, nullable=False)
    meal_type = Column(String(20), nullable=False)  # e.g., 'breakfast', 'lunch', 'dinner'
    calories = Column(Float, nullable=False)
    protein = Column(Float, nullable=False)
    fat = Column(Float, nullable=False)
    carbs = Column(Float, nullable=False)
    sugar = Column(Float, nullable=False)

    user = relationship('User', back_populates='meals')

def init_db():
    Base.metadata.create_all(engine)
