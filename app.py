"""📸 CaloriePic - Rastreador Nutricional Inteligente com Análise de Foto

FUNCIONALIDADES PRINCIPAIS:
- 🔐 Controle de acesso (Login/Cadastro)
- 👤 Gestão de perfis de usuário
- 📸 Análise de foto de refeição (IA)
- 🔍 Consulta código de barras (Open Food Facts)
- 🍴 Parser inteligente: quebra refeições em itens separados
- 💺 Itens individuais salvos no banco (rastreamento granular)
- 📊 Relatórios com fibras e análise nutricional
- 🦪 Análise semanal/mensal com insights do Perplexity
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from db import init_db, SessionLocal, User, Meal, MealItem
from api_perplexity import analyze_meal_by_description
from meal_parser import parse_and_analyze_meal
from nutrition_analysis import get_nutrition_analysis, compare_with_recommendations
import logging
import hashlib

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração
st.set_page_config(
    page_title="📸 CaloriePic",
    page_icon="📸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tema
st.markdown("""
    <style>
        .header { font-size: 2.5em; font-weight: bold; color: #2196F3; }
        .subheader { font-size: 1.5em; font-weight: bold; color: #666; }
        .metric-card { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        .success { color: #4CAF50; font-weight: bold; }
        .warning { color: #ff9800; font-weight: bold; }
        .error { color: #f44336; font-weight: bold; }
        .profile-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
    </style>
""", unsafe_allow_html=True)

# Inicializar DB
try:
    init_db()
except Exception as e:
    logger.error(f"Erro ao inicializar banco de dados: {e}")
    st.error(f"Erro ao inicializar banco de dados: {e}")

# State session
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

if 'user_name' not in st.session_state:
    st.session_state.user_name = None

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if 'last_analysis' not in st.session_state:
    st.session_state.last_analysis = None


# ===================== FUNÇÃO: HASH SENHA =====================
def hash_password(password: str) -> str:
    """Gerar hash SHA256 da senha"""
    return hashlib.sha256(password.encode()).hexdigest()


# ===================== FUNÇÃO: CONSULTAR BARCODE =====================
def query_barcode(barcode: str) -> dict:
    """Consultar Open Food Facts pelo código de barras"""
    import requests
    
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 1:
                product = data.get('product', {})
                return {
                    'success': True,
                    'name': product.get('product_name', 'Desconhecido'),
                    'brand': product.get('brands', 'Desconhecido'),
                    'calories': product.get('nutriments', {}).get('energy-kcal_100g', 0),
                    'protein': product.get('nutriments', {}).get('proteins_100g', 0),
                    'carbs': product.get('nutriments', {}).get('carbohydrates_100g', 0),
                    'fat': product.get('nutriments', {}).get('fat_100g', 0),
                    'fiber': product.get('nutriments', {}).get('fiber_100g', 0)
                }
        
        return {'success': False, 'error': 'Produto não encontrado'}
    
    except Exception as e:
        logger.error(f"Erro ao consultar barcode: {e}")
        return {'success': False, 'error': str(e)}


# ===================== PÁGINA: LOGIN/CADASTRO =====================
if not st.session_state.authenticated:
    st.markdown("""
    <div style='text-align: center; margin-top: 50px;'>
        <h1 style='color: #2196F3; font-size: 3em;'>📸 CaloriePic</h1>
        <p style='font-size: 1.2em; color: #666;'>Rastreador Nutricional Inteligente</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Cadastro"])
    
    # ===== TAB: LOGIN =====
    with tab1:
        st.markdown("### 🔐 Fazer Login")
        
        email_login = st.text_input(
            "Email",
            placeholder="seu@email.com",
            key="email_login"
        )
        
        password_login = st.text_input(
            "Senha",
            type="password",
            placeholder="sua senha",
            key="password_login"
        )
        
        if st.button("🔓 Entrar", use_container_width=True, type="primary"):
            if not email_login or not password_login:
                st.error("⚠️ Preencha email e senha")
            else:
                db = SessionLocal()
                try:
                    user = db.query(User).filter(User.email == email_login).first()
                    
                    if user and user.password_hash == hash_password(password_login):
                        st.session_state.authenticated = True
                        st.session_state.user_id = user.id
                        st.session_state.user_name = user.name
                        st.success(f"✅ Bem-vindo, {user.name}!")
                        st.rerun()
                    else:
                        st.error("❌ Email ou senha incorretos")
                
                except Exception as e:
                    logger.error(f"Erro ao fazer login: {e}")
                    st.error(f"Erro ao fazer login: {e}")
                finally:
                    db.close()
    
    # ===== TAB: CADASTRO =====
    with tab2:
        st.markdown("### 📝 Criar Conta")
        
        name_register = st.text_input(
            "Nome Completo",
            placeholder="Seu nome",
            key="name_register"
        )
        
        email_register = st.text_input(
            "Email",
            placeholder="seu@email.com",
            key="email_register"
        )
        
        password_register = st.text_input(
            "Senha",
            type="password",
            placeholder="Crie uma senha",
            key="password_register"
        )
        
        password_confirm = st.text_input(
            "Confirmar Senha",
            type="password",
            placeholder="Confirme a senha",
            key="password_confirm"
        )
        
        # Dados do Perfil
        st.markdown("#### 👤 Dados do Perfil")
        
        col1, col2 = st.columns(2)
        
        with col1:
            age = st.number_input(
                "Idade",
                min_value=13,
                max_value=120,
                value=30,
                key="age_register"
            )
        
        with col2:
            gender = st.selectbox(
                "Gênero",
                ["Masculino", "Feminino", "Outro"],
                key="gender_register"
            )
        
        col1, col2 = st.columns(2)
        
        with col1:
            height = st.number_input(
                "Altura (cm)",
                min_value=100,
                max_value=250,
                value=170,
                key="height_register"
            )
        
        with col2:
            weight = st.number_input(
                "Peso (kg)",
                min_value=30.0,
                max_value=300.0,
                value=70.0,
                key="weight_register"
            )
        
        activity_level = st.selectbox(
            "Nível de Atividade",
            ["Sedentário", "Leve", "Moderado", "Intenso", "Muito Intenso"],
            key="activity_register"
        )
        
        dietary_goal = st.selectbox(
            "Objetivo Nutricional",
            ["Perder Peso", "Manter Peso", "Ganhar Massa", "Melhorar Saúde"],
            key="goal_register"
        )
        
        if st.button("✅ Criar Conta", use_container_width=True, type="primary"):
            # Validações
            if not all([name_register, email_register, password_register]):
                st.error("⚠️ Preencha todos os campos obrigatórios")
            elif password_register != password_confirm:
                st.error("⚠️ As senhas não coincidem")
            elif len(password_register) < 6:
                st.error("⚠️ A senha deve ter pelo menos 6 caracteres")
            else:
                db = SessionLocal()
                try:
                    # Verificar se email já existe
                    existing_user = db.query(User).filter(User.email == email_register).first()
                    
                    if existing_user:
                        st.error("❌ Este email já está registrado")
                    else:
                        # Criar novo usuário
                        new_user = User(
                            name=name_register,
                            email=email_register,
                            password_hash=hash_password(password_register),
                            age=age,
                            gender=gender.lower(),
                            height_cm=height,
                            weight_kg=weight,
                            activity_level=activity_level.lower().replace(" ", "_"),
                            dietary_goal=dietary_goal.lower().replace(" ", "_")
                        )
                        
                        db.add(new_user)
                        db.commit()
                        
                        st.session_state.authenticated = True
                        st.session_state.user_id = new_user.id
                        st.session_state.user_name = new_user.name
                        
                        st.success(f"✅ Bem-vindo, {new_user.name}! Sua conta foi criada com sucesso.")
                        st.rerun()
                
                except Exception as e:
                    logger.error(f"Erro ao criar conta: {e}")
                    st.error(f"Erro ao criar conta: {e}")
                finally:
                    db.close()


# ===================== APP AUTENTICADO =====================
else:
    # ===================== HEADER =====================
    st.markdown(f"<div class='header'>📸 CaloriePic - Bem-vindo, {st.session_state.user_name}!</div>", unsafe_allow_html=True)
    st.markdown("Analise refeições com precisão, visualize padrões, otimize sua nutrição.")
    st.divider()
    
    # ===================== SIDEBAR =====================
    with st.sidebar:
        st.markdown("### 📊 Menu")
        
        # Perfil do usuário
        with st.expander("👤 Meu Perfil", expanded=False):
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == st.session_state.user_id).first()
                
                if user:
                    st.markdown(f"**Nome:** {user.name}")
                    st.markdown(f"**Email:** {user.email}")
                    st.markdown(f"**Idade:** {user.age} anos")
                    st.markdown(f"**Altura:** {user.height_cm} cm")
                    st.markdown(f"**Peso:** {user.weight_kg} kg")
                    st.markdown(f"**Atividade:** {user.activity_level.replace('_', ' ').title()}")
                    st.markdown(f"**Objetivo:** {user.dietary_goal.replace('_', ' ').title()}")
                    
                    if st.button("✏️ Editar Perfil", use_container_width=True):
                        st.info("Funcionalidade de edição em desenvolvimento")
            
            except Exception as e:
                logger.error(f"Erro ao carregar perfil: {e}")
            finally:
                db.close()
        
        page = st.radio(
            "Escolha uma opção:",
            [
                "Registrar Refeição",
                "Análise de Foto",
                "Consultar Código de Barras",
                "Histórico",
                "Relatórios",
                "Configurações"
            ]
        )
        
        st.divider()
        
        if st.button("🔓 Sair", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.user_name = None
            st.rerun()
    
    
    # ===================== PÁGINA: REGISTRAR REFEIÇÃO =====================
    if page == "Registrar Refeição":
        st.markdown("<div class='subheader'>💫 Registrar Nova Refeição</div>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            meal_date = st.date_input("Data", value=datetime.now())
        
        with col2:
            meal_type = st.selectbox(
                "Tipo de Refeição",
                ["Café da manhã", "Almoço", "Lanche", "Jantar"]
            )
        
        with col3:
            location = st.text_input("Local", placeholder="Ex: Casa, Restaurante...")
        
        st.markdown("#### Descrição da Refeição")
        
        meal_description = st.text_area(
            "Descreva tudo que comeu (separado por vírgulas):",
            placeholder="Ex: 100g de espaghetti a alho e óleo, 1 bife médio à milanesa, salada de alface, um pedaço de pudim",
            height=100
        )
        
        # Botão de análise
        if st.button("🔍 Analisar Refeição", use_container_width=True, type="primary"):
            if not meal_description.strip():
                st.error("⚠️ Por favor, descreva a refeição")
            else:
                with st.spinner("🔍 Analisando refeição..."):
                    # Fazer parse e análise
                    analysis_result = parse_and_analyze_meal(meal_description)
                    
                    if analysis_result['success']:
                        st.session_state.last_analysis = analysis_result
                        
                        # Exibir itens individuais
                        st.markdown("### 💪 Itens Identificados")
                        
                        for idx, item in enumerate(analysis_result['items'], 1):
                            col1, col2, col3 = st.columns([2, 2, 2])
                            
                            with col1:
                                st.write(f"**{idx}. {item['item']}**")
                                st.caption(f"Quantidade: {item['quantity']}")
                            
                            if item.get('nutrients'):
                                with col2:
                                    st.metric("Calorias", f"{item['nutrients'].get('calories', 0):.0f} kcal")
                                with col3:
                                    st.metric("Proteínas", f"{item['nutrients'].get('protein', 0):.1f}g")
                            else:
                                st.warning(f"Erro ao analisar: {item.get('error')}")
                        
                        # Totais da refeição
                        st.markdown("### 📊 RESUMO TOTAL DA REFEIÇÃO")
                        
                        totals = analysis_result['totals']
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("🔥 Calorias", f"{totals.get('calories', 0):.0f} kcal")
                        with col2:
                            st.metric("🥩 Proteínas", f"{totals.get('protein', 0):.1f}g")
                        with col3:
                            st.metric("🍞 Carboidratos", f"{totals.get('carbs', 0):.1f}g")
                        with col4:
                            st.metric("🌾 Fibras", f"{totals.get('fiber', 0):.1f}g")
                        
                        # Botão para salvar
                        if st.button("💾 Salvar Refeição", use_container_width=True):
                            db = SessionLocal()
                            try:
                                # Normalizar meal_type
                                meal_type_normalized = meal_type.lower().replace("ã", "a").replace(" ", "_").replace("da_manha", "breakfast").replace("almoco", "lunch").replace("lanche", "snack").replace("jantar", "dinner")
                                
                                # Criar refeição
                                meal = Meal(
                                    user_id=st.session_state.user_id,
                                    date=meal_date.strftime('%Y-%m-%d'),
                                    meal_type=meal_type_normalized,
                                    description=meal_description,
                                    location_name=location or None,
                                    calories=totals.get('calories', 0),
                                    protein=totals.get('protein', 0),
                                    carbs=totals.get('carbs', 0),
                                    fat_total=totals.get('fat_total', 0),
                                    fat_saturated=totals.get('fat_saturated', 0),
                                    sugar=totals.get('sugar', 0),
                                    fiber=totals.get('fiber', 0),
                                    sodium=totals.get('sodium', 0),
                                    potassium=totals.get('potassium', 0),
                                    cholesterol=totals.get('cholesterol', 0)
                                )
                                
                                # Adicionar itens individuais
                                for order, item_data in enumerate(analysis_result['items']):
                                    item = MealItem(
                                        meal=meal,
                                        item_name=item_data['item'],
                                        quantity=item_data['quantity'],
                                        order=order,
                                        calories=item_data.get('nutrients', {}).get('calories', 0),
                                        protein=item_data.get('nutrients', {}).get('protein', 0),
                                        carbs=item_data.get('nutrients', {}).get('carbs', 0),
                                        fat_total=item_data.get('nutrients', {}).get('fat_total', 0),
                                        fat_saturated=item_data.get('nutrients', {}).get('fat_saturated', 0),
                                        sugar=item_data.get('nutrients', {}).get('sugar', 0),
                                        fiber=item_data.get('nutrients', {}).get('fiber', 0),
                                        sodium=item_data.get('nutrients', {}).get('sodium', 0),
                                        potassium=item_data.get('nutrients', {}).get('potassium', 0),
                                        cholesterol=item_data.get('nutrients', {}).get('cholesterol', 0)
                                    )
                                    meal.items.append(item)
                                
                                # Salvar ao banco
                                db.add(meal)
                                db.commit()
                                
                                st.success("✅ Refeição salva com sucesso! 🙋")
                                st.session_state.last_analysis = None  # Limpar
                            
                            except Exception as e:
                                logger.error(f"Erro ao salvar refeição: {e}")
                                st.error(f"⚠️ Erro ao salvar: {e}")
                            finally:
                                db.close()
                    else:
                        st.error(f"⚠️ Erro na análise: {analysis_result.get('error')}")
    
    
    # ===================== PÁGINA: ANÁLISE DE FOTO =====================
    elif page == "Análise de Foto":
        st.markdown("<div class='subheader'>📸 Análise de Foto da Refeição</div>", unsafe_allow_html=True)
        
        st.info("🚀 Funcionalidade de análise de foto em desenvolvimento - em breve!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📷 Upload de Foto")
            uploaded_file = st.file_uploader("Envie uma foto da refeição", type=["jpg", "jpeg", "png"])
            
            if uploaded_file:
                st.image(uploaded_file, caption="Foto enviada", use_container_width=True)
        
        with col2:
            st.markdown("#### ℹ️ Como Funciona")
            st.markdown("""
            - Envie a foto de sua refeição
            - A IA vai identificar os alimentos
            - Análise nutricional automática
            - Salve diretamente no histórico
            """)
    
    
    # ===================== PÁGINA: CONSULTAR CÓDIGO DE BARRAS =====================
    elif page == "Consultar Código de Barras":
        st.markdown("<div class='subheader'>🔍 Consultar Código de Barras</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            barcode = st.text_input(
                "Código de Barras (EAN/UPC)",
                placeholder="Exemplo: 7891000325144"
            )
        
        with col2:
            st.write("")
            search_button = st.button("🔍 Buscar", use_container_width=True)
        
        if search_button and barcode:
            with st.spinner("🔍 Consultando Open Food Facts..."):
                result = query_barcode(barcode)
                
                if result['success']:
                    st.success("✅ Produto encontrado!")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**Produto:** {result['name']}")
                        st.markdown(f"**Marca:** {result['brand']}")
                    
                    with col2:
                        st.metric("Calorias (100g)", f"{result['calories']:.0f} kcal")
                        st.metric("Proteínas", f"{result['protein']:.1f}g")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Carboidratos", f"{result['carbs']:.1f}g")
                    with col2:
                        st.metric("Gordura", f"{result['fat']:.1f}g")
                    with col3:
                        st.metric("Fibras", f"{result['fiber']:.1f}g")
                    with col4:
                        st.write("")
                else:
                    st.error(f"❌ Erro: {result['error']}")
        
        elif search_button:
            st.error("⚠️ Digite um código de barras válido")
    
    
    # ===================== PÁGINA: HISTÓRICO =====================
    elif page == "Histórico":
        st.markdown("<div class='subheader'>📑 Histórico de Refeições</div>", unsafe_allow_html=True)
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            start_date = st.date_input("Data Inicial", value=datetime.now() - timedelta(days=7))
        with col2:
            end_date = st.date_input("Data Final", value=datetime.now())
        with col3:
            meal_filter = st.multiselect(
                "Tipo de Refeição",
                ["breakfast", "lunch", "snack", "dinner"],
                default=["breakfast", "lunch", "snack", "dinner"]
            )
        
        # Buscar dados
        db = SessionLocal()
        try:
            meals = db.query(Meal).filter(
                Meal.user_id == st.session_state.user_id,
                Meal.date >= start_date.strftime('%Y-%m-%d'),
                Meal.date <= end_date.strftime('%Y-%m-%d')
            ).all()
            
            if meals:
                # Montar DataFrame
                data = []
                for meal in meals:
                    data.append({
                        'Data': meal.date,
                        'Refeição': meal.meal_type.title(),
                        'Descrição': meal.description[:50] + '...' if len(meal.description) > 50 else meal.description,
                        'Calorias': meal.calories,
                        'Proteínas (g)': meal.protein,
                        'Carboidratos (g)': meal.carbs,
                        'Fibras (g)': meal.fiber,
                        'Açúcares (g)': meal.sugar,
                        'Local': meal.location_name or '-'
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)
                
                # Resumo rápido
                st.markdown("### 📊 Resumo do Período")
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("🔥 Calorias Total", f"{df['Calorias'].sum():.0f}")
                with col2:
                    st.metric("🥩 Proteínas", f"{df['Proteínas (g)'].sum():.1f}g")
                with col3:
                    st.metric("🍞 Carboidratos", f"{df['Carboidratos (g)'].sum():.1f}g")
                with col4:
                    st.metric("🌾 Fibras", f"{df['Fibras (g)'].sum():.1f}g")
                with col5:
                    st.metric("💪 Refeições", len(df))
            else:
                st.info("📄 Nenhuma refeição registrada no período selecionado")
        
        except Exception as e:
            logger.error(f"Erro ao buscar histórico: {e}")
            st.error(f"Erro ao buscar histórico: {e}")
        
        finally:
            db.close()
    
    
    # ===================== PÁGINA: RELATÓRIOS =====================
    elif page == "Relatórios":
        st.markdown("<div class='subheader'>📋 Relatórios Nutricionais</div>", unsafe_allow_html=True)
        
        # Opção de período
        period_type = st.radio(
            "Escolha o período:",
            ["Semanal", "Mensal"],
            horizontal=True
        )
        
        if period_type == "Semanal":
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            period_name = "SEMANAL"
        else:
            end_date = datetime.now()
            start_date = datetime(end_date.year, end_date.month, 1)
            period_name = "MENSAL"
        
        # Buscar dados
        db = SessionLocal()
        try:
            meals = db.query(Meal).filter(
                Meal.user_id == st.session_state.user_id,
                Meal.date >= start_date.strftime('%Y-%m-%d'),
                Meal.date <= end_date.strftime('%Y-%m-%d')
            ).all()
            
            if meals:
                # Calcular agregados
                days_count = (end_date - start_date).days + 1
                
                period_data = {
                    'days_count': days_count,
                    'meals_count': len(meals),
                    'calories': sum(m.calories for m in meals),
                    'protein': sum(m.protein for m in meals),
                    'carbs': sum(m.carbs for m in meals),
                    'sugar': sum(m.sugar for m in meals),
                    'fiber': sum(m.fiber for m in meals),
                    'fat_total': sum(m.fat_total for m in meals),
                    'fat_saturated': sum(m.fat_saturated for m in meals),
                    'sodium': sum(m.sodium for m in meals),
                    'potassium': sum(m.potassium for m in meals),
                    'cholesterol': sum(m.cholesterol for m in meals)
                }
                
                # Exibir métricas
                st.markdown(f"### 📋 Resumo {period_name}")
                
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric(
                        "🔥 Calorias",
                        f"{period_data['calories']/days_count:.0f} kcal/dia",
                        delta=f"Total: {period_data['calories']:.0f}"
                    )
                with col2:
                    st.metric(
                        "🥩 Proteínas",
                        f"{period_data['protein']/days_count:.1f}g/dia",
                        delta=f"Total: {period_data['protein']:.1f}g"
                    )
                with col3:
                    st.metric(
                        "🍞 Carboidratos",
                        f"{period_data['carbs']/days_count:.1f}g/dia",
                        delta=f"Total: {period_data['carbs']:.1f}g"
                    )
                with col4:
                    st.metric(
                        "🌾 Fibras",
                        f"{period_data['fiber']/days_count:.1f}g/dia",
                        delta=f"Total: {period_data['fiber']:.1f}g"
                    )
                with col5:
                    st.metric(
                        "📚 Açúcares",
                        f"{period_data['sugar']/days_count:.1f}g/dia",
                        delta=f"Total: {period_data['sugar']:.1f}g"
                    )
                
                # ANÁLISE COM PERPLEXITY (apenas semanal/mensal)
                st.markdown(f"### 🦪 Análise Nutricional - {period_name}")
                
                with st.spinner("🔍 Gerando análise nutricional..."):
                    try:
                        analysis = get_nutrition_analysis(period_data, period_type.lower())
                        st.markdown(analysis)
                    except Exception as e:
                        logger.error(f"Erro ao gerar análise: {e}")
                        st.warning(f"Não foi possível gerar análise: {e}")
                
                # Comparação com recomendações
                st.markdown("### 🎨 Comparação com Recomendações")
                
                try:
                    comparison = compare_with_recommendations(period_data)
                    
                    comp_data = []
                    for nutrient, data in comparison.items():
                        status_emoji = "✅" if data['status'] in ['excellent', 'good'] else "🙋" if data['status'] == 'moderate' else "⚠️"
                        
                        comp_data.append({
                            'Nutriente': nutrient.replace('_', ' ').title(),
                            'Valor': f"{data['value']:.1f}",
                            'Meta': f"{data['target']:.1f}",
                            'Percentual': f"{data['percentage']:.0f}%",
                            'Status': status_emoji
                        })
                    
                    comp_df = pd.DataFrame(comp_data)
                    st.dataframe(comp_df, use_container_width=True)
                
                except Exception as e:
                    logger.error(f"Erro ao comparar com recomendações: {e}")
                    st.warning(f"Não foi possível gerar comparação: {e}")
                
            else:
                st.info("📄 Nenhuma refeição registrada no período selecionado")
        
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            st.error(f"Erro ao gerar relatório: {e}")
        
        finally:
            db.close()
    
    
    # ===================== PÁGINA: CONFIGURAÇÕES =====================
    elif page == "Configurações":
        st.markdown("<div class='subheader'>⚙️ Configurações do App</div>", unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["ℹ️ Sobre", "🔧 Preferências", "📞 Suporte"])
        
        with tab1:
            st.markdown("### 📸 CaloriePic v2.6")
            st.markdown("""
            **Rastreador Nutricional Inteligente com Análise de Foto**
            
            **Funcionalidades:**
            - 🔐 Controle de acesso e perfis de usuário
            - 📸 Análise de foto de refeição (IA)
            - 🔍 Consulta código de barras (Open Food Facts)
            - 🍴 Parser inteligente com quebra em itens
            - 📊 Relatórios nutricionais com Perplexity
            - 🦪 Análise semanal/mensal com insights
            
            **Desenvolvido com ❤️**
            """)
        
        with tab2:
            st.markdown("### 🔧 Preferências")
            st.info("Seção de preferências em desenvolvimento")
        
        with tab3:
            st.markdown("### 📞 Suporte")
            st.markdown("""
            Dúvidas ou problemas?
            - 📧 Email: suporte@calorieic.app
            - 🐛 Reportar bug: github.com/sansquer77/Caloriadev
            - 💬 Discord: [em breve]
            """)


# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #999; font-size: 0.85em;'>
👋 Desenvolvido com ❤️ | Rastreador Nutricional Inteligente | v2.6
</div>
""", unsafe_allow_html=True)
