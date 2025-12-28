from sqlalchemy import create_engine, Column, Integer, Float, Date, String, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
from datetime import datetime

# Configurar string de conexão via variável ambiente para segurança
# Prioridade: DATABASE_URL > MYSQL_CONNECTION_STRING > SQLite local (fallback)
# Formato MySQL: mysql+pymysql://usuario:senha@host:porta/database
# Formato PostgreSQL: postgresql://usuario:senha@host:porta/database

# Caminho do banco SQLite local (fallback quando não há variável de ambiente)
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'caloria.db')
DEFAULT_SQLITE_URL = f'sqlite:///{SQLITE_PATH}'

DB_URL = os.getenv(
    'DATABASE_URL', 
    os.getenv(
        'MYSQL_CONNECTION_STRING', 
        DEFAULT_SQLITE_URL  # Fallback para SQLite local
    )
)

# Digital Ocean usa 'postgres://' mas SQLAlchemy precisa de 'postgresql://'
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)

# Configurações do engine baseadas no tipo de banco
engine_kwargs = {
    'pool_pre_ping': True,
}

# Configurações específicas por tipo de banco
if 'sqlite' in DB_URL:
    # SQLite não suporta pool_recycle e precisa de check_same_thread=False para Streamlit
    engine_kwargs['connect_args'] = {'check_same_thread': False}
elif 'mysql' in DB_URL:
    engine_kwargs['pool_recycle'] = 3600  # Reconecta após 1 hora
    # Adiciona charset para MySQL
    if 'charset' not in DB_URL:
        if '?' in DB_URL:
            DB_URL += '&charset=utf8mb4'
        else:
            DB_URL += '?charset=utf8mb4'
elif 'postgresql' in DB_URL:
    engine_kwargs['pool_recycle'] = 3600

engine = create_engine(DB_URL, **engine_kwargs)
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
