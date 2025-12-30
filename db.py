"""💾 Banco de Dados - Modelos SQLAlchemy

Estrutura:
- users: Autenticação + Perfil Nutricional
- meals: Refeições consolidadas (por data/tipo)
- meal_items: NOVO - Itens individuais dentro de uma refeição
- taco_foods: Referência TACO (opcional)
- open_food_facts_cache: Cache consolidado OFF
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime, date
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./caloria.db')

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """👤 Modelo de Usuário com Perfil Nutricional"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    
    # ===== AUTENTICAÇÃO =====
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    
    # ===== PERFIL BÁSICO =====
    nome_completo = Column(String(200), nullable=True)
    genero = Column(String(20), nullable=True)  # masculino, feminino, outro
    data_nascimento = Column(Date, nullable=True)  # Para cálculo de idade
    
    # ===== DADOS FÍSICOS =====
    altura_cm = Column(Float, nullable=True)      # Altura em cm (ex: 170)
    peso_kg = Column(Float, nullable=True)        # Peso em kg (ex: 75.5)
    gordura_corporal_pct = Column(Float, nullable=True)  # Percentual de gordura
    
    # ===== METAS NUTRICIONAIS (Diárias) =====
    calorias_diarias = Column(Float, nullable=True)        # Calorias alvo/dia
    proteina_pct = Column(Float, default=30, nullable=True)         # % do total de calorias
    carboidrato_pct = Column(Float, default=40, nullable=True)      # % do total de calorias
    gordura_pct = Column(Float, default=30, nullable=True)          # % do total de calorias
    
    # ===== PREFERÉNCIAS =====
    nivel_atividade = Column(String(50), nullable=True)  # sedentario, leve, moderado, intenso, muito_intenso
    objetivo_nutricional = Column(String(100), nullable=True)  # perder_peso, manter, ganhar_massa, melhorar_saude
    
    # ===== AUDITORIA =====
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ===== RELAÇÕES =====
    meals = relationship("Meal", back_populates="user", cascade="all, delete-orphan")


class Meal(Base):
    """🍴 Modelo de Refeição (consolidada)"""
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Data e tipo
    date = Column(String(10), index=True)  # YYYY-MM-DD
    meal_type = Column(String(20), index=True)  # breakfast, lunch, dinner, snack
    
    # Descrição original
    description = Column(Text)  # Descrição completa da refeição
    
    # Nutrientes CONSOLIDADOS (soma dos itens)
    calories = Column(Float, default=0)
    protein = Column(Float, default=0)
    carbs = Column(Float, default=0)
    fat_total = Column(Float, default=0)
    fat_saturated = Column(Float, default=0)
    sugar = Column(Float, default=0)
    fiber = Column(Float, default=0)
    sodium = Column(Float, default=0)
    potassium = Column(Float, default=0)
    cholesterol = Column(Float, default=0)
    
    # Metadados
    location_name = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    user = relationship("User", back_populates="meals")
    items = relationship("MealItem", back_populates="meal", cascade="all, delete-orphan")


class MealItem(Base):
    """🍲 Modelo de Item Individual dentro de uma Refeição (NOVO)"""
    __tablename__ = "meal_items"

    id = Column(Integer, primary_key=True, index=True)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=False)
    
    # Item
    item_name = Column(String(255), nullable=False)  # Ex: "Espaghetti a alho e óleo"
    quantity = Column(String(50), nullable=False)     # Ex: "100g"
    
    # Nutrientes DO ITEM
    calories = Column(Float, default=0)
    protein = Column(Float, default=0)
    carbs = Column(Float, default=0)
    fat_total = Column(Float, default=0)
    fat_saturated = Column(Float, default=0)
    sugar = Column(Float, default=0)
    fiber = Column(Float, default=0)
    sodium = Column(Float, default=0)
    potassium = Column(Float, default=0)
    cholesterol = Column(Float, default=0)
    
    # Ordem do item na refeição
    order = Column(Integer, default=0)
    
    # Metadados
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relação
    meal = relationship("Meal", back_populates="items")


class TacoFood(Base):
    """📋 Tabela de Referência - Alimentos TACO (Tabela de Composição de Alimentos)"""
    __tablename__ = "taco_foods"

    id = Column(Integer, primary_key=True, index=True)
    food_name = Column(String(255), unique=True, index=True)
    
    # Nutrientes por 100g
    calories = Column(Float)
    protein = Column(Float)
    carbs = Column(Float)
    fat_total = Column(Float)
    fat_saturated = Column(Float)
    sugar = Column(Float)
    fiber = Column(Float)
    sodium = Column(Float)
    potassium = Column(Float)
    cholesterol = Column(Float)
    
    # Metadados
    portion_size = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class OpenFoodFactsCache(Base):
    """🔍 Cache de Open Food Facts consolidado em SQLite"""
    __tablename__ = "open_food_facts_cache"

    id = Column(Integer, primary_key=True, index=True)
    food_name = Column(String(255), index=True)  # Nome normalizado
    barcode = Column(String(20), unique=True, index=True)  # Código de barras
    
    product_name = Column(String(255))
    brand = Column(String(255))
    
    # Nutrientes por 100g
    calories = Column(Float)
    protein = Column(Float)
    fat_total = Column(Float)
    fat_saturated = Column(Float)
    carbs = Column(Float)
    sugar = Column(Float)
    fiber = Column(Float)
    sodium = Column(Float)
    potassium = Column(Float)
    cholesterol = Column(Float)
    
    # Metadados
    nutrition_grade = Column(String(5))  # A-E
    serving_size = Column(String(50))
    image_url = Column(Text)
    
    # Rastreamento
    cached_at = Column(DateTime, default=datetime.utcnow)
    accessed_at = Column(DateTime, default=datetime.utcnow, index=True)
    hits = Column(Integer, default=0)  # Contador de acessos
    include_in_backup = Column(Boolean, default=True)  # Controle de backup
    
    # Índices
    __table_args__ = (
        # Índices criados aqui
    )


def init_db():
    """🔧 Inicializa o banco de dados - cria todas as tabelas."""
    print("\n💾 Inicializando banco de dados...")
    
    # Criar tabelas
    Base.metadata.create_all(bind=engine)
    
    print("✅ Tabelas criadas:")
    print("  - users (com perfil nutricional)")
    print("  - meals")
    print("  - meal_items (NOVO)")
    print("  - taco_foods")
    print("  - open_food_facts_cache")
    print()
    
    # Criar índices
    with engine.connect() as conn:
        try:
            # Índices para performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_meals_user_date ON meals(user_id, date)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_meals_meal_type ON meals(meal_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_meal_items_meal ON meal_items(meal_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_off_cache_food_name ON open_food_facts_cache(food_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_off_cache_accessed ON open_food_facts_cache(accessed_at)"
            )
            conn.commit()
            print("✅ Índices criados para performance\n")
        except Exception as e:
            print(f"⚠️ Aviso ao criar índices: {e}\n")


def get_db():
    """Dependency para session do banco."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Compatibilidade com código existente: expor `Session` e helpers de sessão
Session = SessionLocal

from contextlib import contextmanager


@contextmanager
def get_db_session():
    """Context manager que fornece uma sessão SQLAlchemy."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session():
    """Retorna uma nova sessão SQLAlchemy (não gerenciador de contexto)."""
    return SessionLocal()


# ===== EXPORTAR SQLITE_PATH PARA COMPATIBILIDADE =====
# Converte DATABASE_URL para caminho de arquivo se for SQLite
SQLITE_PATH = DATABASE_URL
if SQLITE_PATH.startswith('sqlite:///'):
    SQLITE_PATH = SQLITE_PATH.replace('sqlite:///', '')
elif SQLITE_PATH.startswith('sqlite://'):
    SQLITE_PATH = SQLITE_PATH.replace('sqlite://', '')
