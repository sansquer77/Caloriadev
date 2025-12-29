"""📸 CaloriePic - Rastreador Nutricional Inteligente com Análise de Foto

FUNCIONALIDADES PRINCIPAIS:
- 🔐 Controle de acesso (Login/Cadastro)
- 👤 Gestão de perfis de usuário com dados nutricionais
- 📸 Análise de foto de refeição (IA GEMINI)
- 🔍 Consulta código de barras (Open Food Facts)
- 🍴 Parser inteligente: quebra refeições em itens separados
- 💺 Itens individuais salvos no banco (rastreamento granular)
- 📊 Relatórios com fibras e análise nutricional
- 🦪 Análise semanal/mensal com insights do Perplexity
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
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
if 'username' not in st.session_state:
    st.session_state.username = None
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'last_analysis' not in st.session_state:
    st.session_state.last_analysis = None


# ===================== FUNÇÕES AUX ======================
def hash_password(password: str) -> str:
    """Gerar hash SHA256 da senha"""
    return hashlib.sha256(password.encode()).hexdigest()


def calcular_idade(data_nascimento: date) -> int:
    """Calcular idade a partir da data de nascimento"""
    hoje = date.today()
    idade = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        idade -= 1
    return idade


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
                    
                    if user and user.hashed_password == hash_password(password_login):
                        st.session_state.authenticated = True
                        st.session_state.user_id = user.id
                        st.session_state.username = user.username
                        st.success(f"✅ Bem-vindo, {user.nome_completo or user.username}!")
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
        
        # Dados de autenticação
        col1, col2 = st.columns(2)
        with col1:
            nome_completo = st.text_input(
                "Nome Completo",
                placeholder="Seu nome",
                key="nome_register"
            )
        with col2:
            username_register = st.text_input(
                "Nome de Usuário",
                placeholder="usuario123",
                key="username_register"
            )
        
        email_register = st.text_input(
            "Email",
            placeholder="seu@email.com",
            key="email_register"
        )
        
        password_register = st.text_input(
            "Senha",
            type="password",
            placeholder="Crie uma senha (min. 6 caracteres)",
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
            genero = st.selectbox(
                "Gênero",
                ["Masculino", "Feminino", "Outro"],
                key="genero_register"
            )
        with col2:
            # ✅ CORRIGIDO: Data de nascimento SEM LIMITE SUPERIOR
            data_nascimento = st.date_input(
                "Data de Nascimento",
                value=date(1977, 1, 1),  # Padrão para ~48 anos
                min_value=date(1920, 1, 1),  # Nascido em 1920 ou depois (limite realista)
                max_value=date.today(),  # Não permite data futura
                key="data_nascimento_register"
            )
        
        col1, col2 = st.columns(2)
        with col1:
            altura_cm = st.number_input(
                "Altura (cm)",
                min_value=100,
                max_value=250,
                value=170,
                key="altura_register"
            )
        with col2:
            peso_kg = st.number_input(
                "Peso (kg)",
                min_value=30.0,
                max_value=300.0,
                value=70.0,
                key="peso_register"
            )
        
        gordura_corporal_pct = st.number_input(
            "% Gordura Corporal (opcional)",
            min_value=0.0,
            max_value=60.0,
            value=20.0,
            step=0.5,
            key="gordura_register"
        )
        
        # Metas nutricionais
        st.markdown("#### 🍾 Metas Nutricionais (Diárias)")
        
        calorias_diarias = st.number_input(
            "Calorias alvo por dia (kcal)",
            min_value=1000,
            max_value=5000,
            value=2000,
            key="calorias_register"
        )
        
        col1, col2, col3 = st.columns(3)
        with col1:
            proteina_pct = st.number_input(
                "% Proteína",
                min_value=10,
                max_value=50,
                value=30,
                key="proteina_pct"
            )
        with col2:
            carboidrato_pct = st.number_input(
                "% Carboidrato",
                min_value=20,
                max_value=70,
                value=40,
                key="carboidrato_pct"
            )
        with col3:
            gordura_pct = st.number_input(
                "% Gordura",
                min_value=10,
                max_value=50,
                value=30,
                key="gordura_pct"
            )
        
        # Verificar se soma 100%
        total_pct = proteina_pct + carboidrato_pct + gordura_pct
        if total_pct != 100:
            st.warning(f"⚠️ A soma dos percentuais deve ser 100% (atual: {total_pct}%")
        
        # Preferências
        st.markdown("#### 🌟 Preferências")
        
        col1, col2 = st.columns(2)
        with col1:
            nivel_atividade = st.selectbox(
                "Nível de Atividade",
                ["Sedentário", "Leve", "Moderado", "Intenso", "Muito Intenso"],
                key="atividade_register"
            )
        with col2:
            objetivo_nutricional = st.selectbox(
                "Objetivo Nutricional",
                ["Perder Peso", "Manter Peso", "Ganhar Massa", "Melhorar Saúde"],
                key="objetivo_register"
            )
        
        if st.button("✅ Criar Conta", use_container_width=True, type="primary"):
            # Validações
            errors = []
            if not all([nome_completo, username_register, email_register, password_register]):
                errors.append("⚠️ Preencha todos os campos obrigatórios")
            if password_register != password_confirm:
                errors.append("⚠️ As senhas não coincidem")
            if len(password_register) < 6:
                errors.append("⚠️ A senha deve ter pelo menos 6 caracteres")
            if total_pct != 100:
                errors.append(f"⚠️ A soma dos percentuais deve ser 100% (atual: {total_pct}%)")
            
            # Validar idade
            idade_user = calcular_idade(data_nascimento)
            if idade_user < 13:
                errors.append(f"⚠️ Você deve ter pelo menos 13 anos (sua idade: {idade_user} anos)")
            if idade_user > 120:
                errors.append(f"⚠️ Data de nascimento inválida (seria {idade_user} anos)")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                db = SessionLocal()
                try:
                    # Verificar se email/username já existem
                    existing_email = db.query(User).filter(User.email == email_register).first()
                    existing_username = db.query(User).filter(User.username == username_register).first()
                    
                    if existing_email:
                        st.error("❌ Este email já está registrado")
                    elif existing_username:
                        st.error("❌ Este nome de usuário já está em uso")
                    else:
                        # Criar novo usuário
                        new_user = User(
                            username=username_register,
                            email=email_register,
                            hashed_password=hash_password(password_register),
                            nome_completo=nome_completo,
                            genero=genero.lower(),
                            data_nascimento=data_nascimento,
                            altura_cm=float(altura_cm),
                            peso_kg=float(peso_kg),
                            gordura_corporal_pct=float(gordura_corporal_pct),
                            calorias_diarias=float(calorias_diarias),
                            proteina_pct=float(proteina_pct),
                            carboidrato_pct=float(carboidrato_pct),
                            gordura_pct=float(gordura_pct),
                            nivel_atividade=nivel_atividade.lower().replace(" ", "_"),
                            objetivo_nutricional=objetivo_nutricional.lower().replace(" ", "_")
                        )
                        
                        db.add(new_user)
                        db.commit()
                        
                        st.session_state.authenticated = True
                        st.session_state.user_id = new_user.id
                        st.session_state.username = new_user.username
                        
                        st.success(f"✅ Bem-vindo, {new_user.nome_completo}! Sua conta foi criada com sucesso.")
                        st.rerun()
                
                except Exception as e:
                    logger.error(f"Erro ao criar conta: {e}")
                    st.error(f"Erro ao criar conta: {e}")
                finally:
                    db.close()


# ===================== APP AUTENTICADO =====================
else:
    # ===================== HEADER =====================
    st.markdown(f"<div class='header'>📸 CaloriePic</div>", unsafe_allow_html=True)
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
                    st.markdown(f"**Nome:** {user.nome_completo}")
                    st.markdown(f"**Email:** {user.email}")
                    
                    # Dados calculados
                    if user.data_nascimento:
                        idade = calcular_idade(user.data_nascimento)
                        st.markdown(f"**Idade:** {idade} anos")
                    
                    st.markdown(f"**Altura:** {user.altura_cm} cm")
                    st.markdown(f"**Peso:** {user.peso_kg} kg")
                    if user.gordura_corporal_pct:
                        st.markdown(f"**Gordura Corporal:** {user.gordura_corporal_pct}%")
                    
                    st.divider()
                    st.markdown("**Metas Diárias:**")
                    st.markdown(f"- 🔥 Calorias: {user.calorias_diarias} kcal")
                    st.markdown(f"- 🥩 Proteína: {user.proteina_pct}%")
                    st.markdown(f"- 🍞 Carboidrato: {user.carboidrato_pct}%")
                    st.markdown(f"- 💼 Gordura: {user.gordura_pct}%")
                    
                    st.divider()
                    if st.button("✏️ Editar Perfil", use_container_width=True):
                        st.info("🚀 Funcionalidade de edição em desenvolvimento")
            
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
            st.session_state.username = None
            st.rerun()
    
    
    # ===================== PÁGINAS DO APP =====================
    
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
                    analysis_result = parse_and_analyze_meal(meal_description)
                    
                    if analysis_result['success']:
                        st.session_state.last_analysis = analysis_result
                        
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
                        
                        if st.button("💾 Salvar Refeição", use_container_width=True):
                            db = SessionLocal()
                            try:
                                meal_type_normalized = meal_type.lower().replace("ã", "a").replace(" ", "_").replace("da_manha", "breakfast").replace("almoco", "lunch").replace("lanche", "snack").replace("jantar", "dinner")
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
                                
                                db.add(meal)
                                db.commit()
                                st.success("✅ Refeição salva com sucesso!")
                                st.session_state.last_analysis = None
                            
                            except Exception as e:
                                logger.error(f"Erro ao salvar refeição: {e}")
                                st.error(f"⚠️ Erro ao salvar: {e}")
                            finally:
                                db.close()
                    else:
                        st.error(f"⚠️ Erro na análise: {analysis_result.get('error')}")
    
    elif page == "Análise de Foto":
        st.markdown("<div class='subheader'>📸 Análise de Foto da Refeição</div>", unsafe_allow_html=True)
        st.info("✅ Análise de foto com IA GEMINI - Enviando foto de uma refeição...")
        
        uploaded_file = st.file_uploader("Faça upload de uma foto da refeição", type=["jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.image(uploaded_file, caption="Foto da Refeição", width=200)
            
            with col2:
                if st.button("🤖 Analisar com GEMINI", use_container_width=True, type="primary"):
                    with st.spinner("🔍 GEMINI analisando imagem..."):
                        try:
                            from api_gemini import analyze_meal_from_image
                            from PIL import Image
                            
                            # Obter meta de calorias do usuário
                            db = SessionLocal()
                            user = db.query(User).filter(User.id == st.session_state.user_id).first()
                            user_calorias = user.calorias_diarias if user else 2000
                            db.close()
                            
                            # Analisar imagem
                            image = Image.open(uploaded_file)
                            analysis_result = analyze_meal_from_image(image, user_calorias)
                            
                            if analysis_result['success']:
                                st.markdown("### 💪 Itens Identificados (GEMINI)")
                                
                                for idx, item in enumerate(analysis_result['items'], 1):
                                    col_a, col_b = st.columns([2, 2])
                                    with col_a:
                                        st.write(f"**{idx}. {item['item']}**")
                                        st.caption(f"Quantidade: {item['quantity']}")
                                    with col_b:
                                        st.metric("Calorias", f"{item.get('calories', 0):.0f} kcal")
                                        st.metric("Proteínas", f"{item.get('protein', 0):.1f}g")
                                
                                if analysis_result.get('observation'):
                                    st.info(f"📝 Observação: {analysis_result['observation']}")
                                
                                st.markdown("### 📊 RESUMO TOTAL")
                                totals = analysis_result['totals']
                                col_1, col_2, col_3, col_4 = st.columns(4)
                                with col_1:
                                    st.metric("🔥 Calorias", f"{totals.get('calories', 0):.0f} kcal")
                                with col_2:
                                    st.metric("🥩 Proteínas", f"{totals.get('protein', 0):.1f}g")
                                with col_3:
                                    st.metric("🍞 Carboidratos", f"{totals.get('carbs', 0):.1f}g")
                                with col_4:
                                    st.metric("🌾 Fibras", f"{totals.get('fiber', 0):.1f}g")
                            else:
                                st.error(f"❌ Erro na análise GEMINI: {analysis_result.get('error')}")
                        
                        except ImportError:
                            st.error("⚠️ Módulo GEMINI não importado. Verifique se api_gemini.py existe.")
                        except Exception as e:
                            logger.error(f"Erro ao analisar foto: {e}")
                            st.error(f"⚠️ Erro: {e}")
    
    elif page == "Consultar Código de Barras":
        st.markdown("<div class='subheader'>🔍 Consultar Código de Barras</div>", unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        with col1:
            barcode = st.text_input("Código de Barras (EAN/UPC)", placeholder="Exemplo: 7891000325144")
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
                else:
                    st.error(f"❌ Erro: {result['error']}")
    
    elif page == "Histórico":
        st.markdown("<div class='subheader'>📑 Histórico de Refeições</div>", unsafe_allow_html=True)
        
        db = SessionLocal()
        try:
            meals = db.query(Meal).filter(Meal.user_id == st.session_state.user_id).order_by(Meal.date.desc()).all()
            
            if meals:
                # Agrupar por data
                meals_by_date = {}
                for meal in meals:
                    date_str = meal.date
                    if date_str not in meals_by_date:
                        meals_by_date[date_str] = []
                    meals_by_date[date_str].append(meal)
                
                # Exibir por data
                for date_str in sorted(meals_by_date.keys(), reverse=True):
                    with st.expander(f"📅 {date_str}"):
                        day_meals = meals_by_date[date_str]
                        day_totals = {
                            'calories': sum(m.calories for m in day_meals),
                            'protein': sum(m.protein for m in day_meals),
                            'carbs': sum(m.carbs for m in day_meals),
                            'fiber': sum(m.fiber for m in day_meals)
                        }
                        
                        # Resumo do dia
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("🔥 Calorias (dia)", f"{day_totals['calories']:.0f} kcal")
                        with col2:
                            st.metric("🥩 Proteínas", f"{day_totals['protein']:.1f}g")
                        with col3:
                            st.metric("🍞 Carboidratos", f"{day_totals['carbs']:.1f}g")
                        with col4:
                            st.metric("🌾 Fibras", f"{day_totals['fiber']:.1f}g")
                        
                        st.divider()
                        
                        # Refeições do dia
                        for meal in day_meals:
                            st.markdown(f"**{meal.meal_type.upper()}** - {meal.description[:50]}...")
                            st.caption(f"📍 {meal.location_name or 'Local não informado'}")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Cal", f"{meal.calories:.0f}")
                            with col2:
                                st.metric("Prot", f"{meal.protein:.1f}g")
                            with col3:
                                st.metric("Carbs", f"{meal.carbs:.1f}g")
                            with col4:
                                st.metric("Fiber", f"{meal.fiber:.1f}g")
                            
                            st.divider()
            else:
                st.info("📭 Nenhuma refeição registrada ainda. Comece adicionando uma!")
        
        except Exception as e:
            logger.error(f"Erro ao carregar histórico: {e}")
            st.error(f"Erro ao carregar histórico: {e}")
        finally:
            db.close()
    
    elif page == "Relatórios":
        st.markdown("<div class='subheader'>📋 Relatórios Nutricionais</div>", unsafe_allow_html=True)
        
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == st.session_state.user_id).first()
            meals = db.query(Meal).filter(Meal.user_id == st.session_state.user_id).all()
            
            if meals:
                # Totais gerais
                total_meals = len(meals)
                total_calories = sum(m.calories for m in meals)
                avg_calories = total_calories / total_meals if total_meals > 0 else 0
                total_protein = sum(m.protein for m in meals)
                avg_protein = total_protein / total_meals if total_meals > 0 else 0
                
                st.markdown("### 📊 Resumo Geral")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total de Refeições", total_meals)
                with col2:
                    st.metric("Média de Calorias", f"{avg_calories:.0f} kcal")
                with col3:
                    st.metric("Total de Proteína", f"{total_protein:.1f}g")
                with col4:
                    st.metric("Média de Proteína/refeição", f"{avg_protein:.1f}g")
                
                st.divider()
                
                # Comparação com meta
                if user:
                    st.markdown(f"### 🎯 Comparação com Suas Metas")
                    st.markdown(f"**Meta diária:** {user.calorias_diarias} kcal")
                    st.markdown(f"**Média consumida:** {avg_calories:.0f} kcal")
                    st.markdown(f"**Diferença:** {avg_calories - user.calorias_diarias:+.0f} kcal")
                    
                    pct_meta = (avg_calories / user.calorias_diarias) * 100
                    st.progress(min(pct_meta / 100, 1.0), text=f"{pct_meta:.0f}% da meta")
                    
                    st.divider()
                    st.markdown("### 💡 Insights com Perplexity (em desenvolvimento)")
                    st.info("🚀 Análise inteligente de hábitos alimentares em breve!")
            else:
                st.info("📭 Nenhuma refeição registrada ainda. Comece adicionando uma!")
        
        except Exception as e:
            logger.error(f"Erro ao gerar relatório: {e}")
            st.error(f"Erro ao gerar relatório: {e}")
        finally:
            db.close()
    
    elif page == "Configurações":
        st.markdown("<div class='subheader'>⚙️ Configurações do App</div>", unsafe_allow_html=True)
        st.info("🚀 Seção em desenvolvimento")


# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #999; font-size: 0.85em;'>
👋 Desenvolvido com ❤️ | Rastreador Nutricional Inteligente | v2.6
</div>
""", unsafe_allow_html=True)
