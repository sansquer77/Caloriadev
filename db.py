"""
Módulo de configuração do banco de dados.
Suporta SQLite (desenvolvimento), MySQL e PostgreSQL (produção).
"""

from sqlalchemy import create_engine, Column, Integer, Float, Date, String, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from contextlib import contextmanager
import os
from datetime import datetime
from typing import Generator

# Configurar string de conexão via variável ambiente para segurança
# Prioridade: DATABASE_URL > MYSQL_CONNECTION_STRING > SQLite local (fallback)

# Caminho do banco SQLite local (fallback quando não há variável de ambiente)
SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'caloria.db')
DEFAULT_SQLITE_URL = f'sqlite:///{SQLITE_PATH}'

DB_URL = os.getenv(
    'DATABASE_URL', 
    os.getenv(
        'MYSQL_CONNECTION_STRING', 
        DEFAULT_SQLITE_URL
    )
)

# Digital Ocean usa 'postgres://' mas SQLAlchemy precisa de 'postgresql://'
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)

# Configurações do engine baseadas no tipo de banco
engine_kwargs = {
    'pool_pre_ping': True,  # Verifica conexão antes de usar
}

# Configurações específicas por tipo de banco
if 'sqlite' in DB_URL:
    engine_kwargs['connect_args'] = {'check_same_thread': False}
elif 'mysql' in DB_URL:
    engine_kwargs['pool_recycle'] = 3600
    engine_kwargs['pool_size'] = 5
    engine_kwargs['max_overflow'] = 10
    if 'charset' not in DB_URL:
        DB_URL += '&charset=utf8mb4' if '?' in DB_URL else '?charset=utf8mb4'
elif 'postgresql' in DB_URL:
    engine_kwargs['pool_recycle'] = 3600
    engine_kwargs['pool_size'] = 5
    engine_kwargs['max_overflow'] = 10

engine = create_engine(DB_URL, **engine_kwargs)
SessionFactory = sessionmaker(bind=engine)
Base = declarative_base()

# Alias para compatibilidade
Session = SessionFactory

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    weight = Column(Float, nullable=True)  # kg
    height = Column(Float, nullable=True)  # meters
    birth_date = Column(Date, nullable=True)  # Data de nascimento
    cal_limit = Column(Float, nullable=True)
    protein_limit = Column(Float, nullable=True)
    fat_limit = Column(Float, nullable=True)
    carbs_limit = Column(Float, nullable=True)
    sugar_limit = Column(Float, nullable=True)
    # Percentuais dos macronutrientes
    protein_pct = Column(Float, nullable=True, default=30.0)  # % de proteína
    fat_pct = Column(Float, nullable=True, default=25.0)  # % de gordura
    carbs_pct = Column(Float, nullable=True, default=45.0)  # % de carboidrato
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
    """Retorna uma nova sessão do banco de dados (uso legado)."""
    return SessionFactory()


@contextmanager
def get_db_session() -> Generator:
    """
    Context manager para sessões de banco de dados.
    Garante que a sessão seja fechada corretamente e faz rollback em caso de erro.
    
    Uso:
        with get_db_session() as session:
            session.query(User).all()
    """
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
