import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from auth import generate_token, decode_token, create_password_hash, verify_password_hash
from api_perplexity import analyze_meal_by_description, analyze_meal_by_barcode, analyze_meal_photo
from nutrition_fixes import safe_session_key, process_gemini_food_items
from models import MealData
from storage import (
    save_meal, get_daily_macros, get_aggregated_macros, create_user,
    get_user_by_username, get_user_by_id, update_user_profile, update_user_password,
    get_user_meals, delete_meal
)
from db import init_db, SQLITE_PATH
import json
import os

# Importações opcionais com fallback (para evitar erro se reportlab não estiver instalado)
BACKUP_AVAILABLE = False
BACKUP_ERROR = None
try:
    from backup import (
        export_to_json, import_from_json, list_backups, delete_backup,
        mysql_dump, mysql_restore, quick_backup
    )
    BACKUP_AVAILABLE = True
except Exception as e:
    BACKUP_ERROR = str(e)
    print(f"Módulo backup não disponível: {e}")

REPORTS_AVAILABLE = False
REPORTS_ERROR = None
try:
    from reports import generate_pdf_report, get_period_dates, get_report_filename
    REPORTS_AVAILABLE = True
except Exception as e:
    REPORTS_ERROR = str(e)
    print(f"Módulo reports não disponível: {e}")

TACO_AVAILABLE = False
TACO_ERROR = None
try:
    from taco_db import init_taco_db, get_taco_stats
    TACO_AVAILABLE = True
except Exception as e:
    TACO_ERROR = str(e)
    print(f"Módulo TACO não disponível: {e}")

# Configuração da página
st.set_page_config(
    page_title="Caloria - Análise Nutricional",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializa o banco de dados
init_db()

# CSS customizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E7D32;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
    }
    .success-msg {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
</style>
""", unsafe_allow_html=True)

# Funções auxiliares
def init_session_state():
    """Inicializa variáveis de sessão com valores padrão."""
    # Variáveis de autenticação
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'current_location' not in st.session_state:
        st.session_state.current_location = None
    
    # Variáveis de análise (para evitar erro ao resetar)
    if 'barcode_quantity' not in st.session_state:
        st.session_state.barcode_quantity = 100
    if 'meal_type' not in st.session_state:
        st.session_state.meal_type = "lunch"
    if 'meal_date' not in st.session_state:
        st.session_state.meal_date = date.today()
    if 'loc_name' not in st.session_state:
        st.session_state.loc_name = ""
    if 'camera' not in st.session_state:
        st.session_state.camera = None
    if 'upload' not in st.session_state:
        st.session_state.upload = None
    if 'desc_input' not in st.session_state:
        st.session_state.desc_input = ""
    if 'barcode_input' not in st.session_state:
        st.session_state.barcode_input = ""

def show_login_page():
    """Exibe página de login/cadastro."""
    st.markdown('<h1 class="main-header">🍽️ Caloria</h1>', unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Análise nutricional inteligente</p>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Cadastro"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Usuário", key="login_user")
            password = st.text_input("Senha", type='password', key="login_pass")
            submit = st.form_submit_button("Entrar", use_container_width=True)
            
            if submit:
                user = get_user_by_username(username)
                if user and verify_password_hash(user['password_hash'], password):
                    st.session_state.user_id = user['id']
                    st.session_state.username = user['username']
                    st.session_state.logged_in = True
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
    
    with tab2:
        with st.form("register_form"):
            st.subheader("Criar nova conta")
            new_username = st.text_input("Usuário", key="reg_user")
            new_password = st.text_input("Senha", type='password', key="reg_pass")
            confirm_password = st.text_input("Confirmar Senha", type='password', key="reg_confirm")
            
            st.divider()
            st.subheader("Dados pessoais (opcional)")
            col1, col2 = st.columns(2)
            with col1:
                weight = st.number_input("⚖️ Peso (kg)", min_value=0.0, max_value=500.0, format="%.1f", key="reg_weight")
                height = st.number_input("📏 Altura (m)", min_value=0.0, max_value=3.0, format="%.2f", key="reg_height")
            with col2:
                birth_date = st.date_input(
                    "🎂 Data de Nascimento",
                    value=date(1990, 1, 1),
                    min_value=date(1920, 1, 1),
                    max_value=date.today(),
                    key="reg_birth"
                )
            
            st.divider()
            st.subheader("Metas nutricionais (opcional)")
            
            cal_limit = st.number_input("🔥 Meta de Calorias (kcal/dia)", min_value=500, max_value=10000, value=2000, step=50, key="reg_cal")
            
            st.caption("Distribuição de macronutrientes (devem somar 100%)")
            col1, col2, col3 = st.columns(3)
            with col1:
                protein_pct = st.slider("🥩 Proteína (%)", min_value=10, max_value=60, value=30, step=5, key="reg_prot_pct")
            with col2:
                fat_pct = st.slider("🧈 Gordura (%)", min_value=10, max_value=60, value=25, step=5, key="reg_fat_pct")
            with col3:
                carbs_pct = st.slider("🍞 Carboidrato (%)", min_value=10, max_value=70, value=45, step=5, key="reg_carbs_pct")
            
            total_pct = protein_pct + fat_pct + carbs_pct
            if total_pct != 100:
                st.warning(f"⚠️ Total: {total_pct}% - Deve somar 100%")
            else:
                st.success(f"✅ Total: {total_pct}%")
                # Calcular gramas
                protein_grams = (cal_limit * protein_pct / 100) / 4
                fat_grams = (cal_limit * fat_pct / 100) / 9
                carbs_grams = (cal_limit * carbs_pct / 100) / 4
                st.caption(f"🥩 {protein_grams:.0f}g | 🧈 {fat_grams:.0f}g | 🍞 {carbs_grams:.0f}g")
            
            submit = st.form_submit_button("Cadastrar", use_container_width=True)
            
            if submit:
                if not new_username or not new_password:
                    st.error("Preencha usuário e senha.")
                elif new_password != confirm_password:
                    st.error("As senhas não coincidem.")
                elif total_pct != 100:
                    st.error("Os percentuais devem somar 100%.")
                elif get_user_by_username(new_username):
                    st.error("Este usuário já existe.")
                else:
                    pwd_hash = create_password_hash(new_password)
                    # Calcular limites em gramas
                    protein_limit = (cal_limit * protein_pct / 100) / 4
                    fat_limit = (cal_limit * fat_pct / 100) / 9
                    carbs_limit = (cal_limit * carbs_pct / 100) / 4
                    
                    user_id = create_user(
                        new_username, pwd_hash, 
                        weight=weight or None, 
                        height=height or None,
                        cal_limit=float(cal_limit),
                        protein_limit=protein_limit,
                        fat_limit=fat_limit,
                        carbs_limit=carbs_limit,
                        sugar_limit=None,
                        birth_date=birth_date,
                        protein_pct=float(protein_pct),
                        fat_pct=float(fat_pct),
                        carbs_pct=float(carbs_pct)
                    )
                    st.success("Conta criada com sucesso! Faça login.")

def show_sidebar():
    """Exibe sidebar com navegação."""
    with st.sidebar:
        st.markdown(f"### 👋 Olá, {st.session_state.username}!")
        st.divider()
        
        page = st.radio(
            "Navegação",
            ["🍽️ Nova Análise", "📊 Resumo Diário", "📈 Histórico", "📄 Relatórios", "👤 Meu Perfil", "💾 Backup/Restore"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Status das APIs
        with st.expander("🔧 Status do Sistema", expanded=False):
            perplexity_key = os.getenv('PERPLEXITY_API_KEY')
            
            if perplexity_key:
                st.success("✅ Perplexity API (Análise + Fallback)")
            else:
                st.error("❌ Perplexity API")
            
            # Status da tabela TACO
            if TACO_AVAILABLE:
                taco_stats = get_taco_stats()
                if taco_stats.get('status') == 'ready':
                    st.success(f"✅ TACO ({taco_stats.get('count', 0)} alimentos)")
                else:
                    st.warning("⚠️ TACO não inicializada")
                    if st.button("📥 Baixar Tabela TACO", key="init_taco"):
                        with st.spinner("Baixando tabela TACO..."):
                            if init_taco_db():
                                st.success("✅ Tabela TACO baixada!")
                                st.rerun()
                            else:
                                st.error("❌ Erro ao baixar tabela")
            else:
                st.warning(f"⚠️ TACO: {TACO_ERROR or 'N/A'}")
            
            if BACKUP_AVAILABLE:
                st.success("✅ Módulo Backup")
            else:
                st.warning(f"⚠️ Backup: {BACKUP_ERROR or 'N/A'}")
            
            if REPORTS_AVAILABLE:
                st.success("✅ Módulo Relatórios")
            else:
                st.warning(f"⚠️ Reports: {REPORTS_ERROR or 'N/A'}")
        
        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.logged_in = False
            st.rerun()
        
        return page

def get_location_component():
    """Componente para capturar localização com suporte a geolocalização automática."""
    st.markdown("#### 📍 Localização")
    
    # Mantém apenas o campo opcional de nome do local (autocomplete)

    # Buscar locais já cadastrados do usuário
    location_options = []
    try:
        user_id = st.session_state.get('user_id', None)
        if user_id:
            meals = get_user_meals(user_id, limit=200)
            location_options = sorted(list(set([m['location_name'] for m in meals if m['location_name']])))
    except Exception as e:
        location_options = []

    # Campo com autocomplete (selectbox com digitação livre)
    if location_options:
        location_name = st.selectbox(
            "Nome do local (opcional)",
            options=["(Novo local)"] + location_options,
            index=0,
            key="loc_name_select",
            help="Escolha um local já cadastrado ou digite um novo."
        )
        if location_name == "(Novo local)":
            location_name = st.text_input("Digite o nome do local", key="loc_name", placeholder="Ex: Restaurante XYZ")
    else:
        location_name = st.text_input("Nome do local (opcional)", placeholder="Ex: Restaurante XYZ", key="loc_name")

    return location_name

def show_analysis_page():
    """Página principal de análise de refeições."""
    st.markdown("## 🍽️ Análise de Refeição")
    
    # Tabs para foto, texto ou código de barras
    tab1, tab2, tab3 = st.tabs(["📷 Tirar Foto", "✍️ Descrever Refeição", "📊 Código de Barras"])
    
    with tab1:
        st.markdown("### 📷 Análise por Foto")
        st.info("💡 Tire uma foto do seu prato ou do rótulo nutricional de um produto.")
        
        img_file = st.camera_input("Capturar foto", key="camera")
        
        # Também permite upload
        uploaded_file = st.file_uploader("Ou faça upload de uma imagem", type=['jpg', 'jpeg', 'png'], key="upload")
        
        image_bytes = None
        if img_file is not None:
            image_bytes = img_file.getvalue()
        elif uploaded_file is not None:
            image_bytes = uploaded_file.getvalue()
        
        if image_bytes:
            st.image(image_bytes, caption="Imagem para análise", use_container_width=True)
    
    with tab2:
        st.markdown("### ✍️ Descreva sua refeição")
        st.info("💡 **Dica:** Seja específico com as quantidades para uma análise mais precisa.")
        
        description_input = st.text_area(
            "O que você comeu?",
            placeholder="Ex: 1 prato de arroz, 100g de frango grelhado, salada de alface com tomate\n\nPara produtos industrializados, use o nome completo: 'Suco de Maçã Yakult 200ml'",
            height=120,
            key="desc_input"
        )
    
    with tab3:
        st.markdown("### 📊 Buscar por Código de Barras")
        st.markdown("Use o código de barras de produtos industrializados para buscar informações nutricionais.")
        
        barcode_input = st.text_input(
            "Código de barras",
            placeholder="Ex: 7894900011517 (Coca-Cola 350ml)",
            key="barcode_input",
            help="Digite o código de barras do produto (EAN-13, UPC, etc.)"
        )
        
        barcode_quantity = st.number_input(
            "Quantidade consumida (gramas ou ml)",
            min_value=1,
            max_value=5000,
            value=st.session_state.get('barcode_quantity', 100),
            step=10,
            key="barcode_quantity",
            help="Informe a quantidade que você consumiu"
        )
        
        st.info("💡 **Dica:** O código de barras geralmente está na embalagem do produto. A busca usa a base de dados Open Food Facts com milhões de produtos.")
    
    st.divider()
    
    # Informações adicionais
    col1, col2 = st.columns(2)
    with col1:
        meal_type = st.selectbox(
            "Tipo de refeição",
            ["breakfast", "lunch", "dinner", "snack"],
            index=1,  # lunch é padrão
            format_func=lambda x: {
                "breakfast": "☀️ Café da manhã",
                "lunch": "🌤️ Almoço", 
                "dinner": "🌙 Jantar",
                "snack": "🍪 Lanche"
            }.get(x, x),
            key="meal_type"
        )
    with col2:
        meal_date = st.date_input("Data", value=date.today(), key="meal_date")
    
    # Localização
    st.divider()
    location_name = get_location_component()
    
    st.divider()
    
    # Botão de análise
    if st.button("🔍 Analisar Refeição", use_container_width=True, type="primary"):
        nutrients = None
        
        # Análise por código de barras (prioridade se preenchido)
        if barcode_input and barcode_input.strip():
            with st.spinner("📊 Buscando produto no Open Food Facts..."):
                nutrients = analyze_meal_by_barcode(barcode_input.strip(), quantity_grams=float(barcode_quantity))
        # Análise por foto
        elif image_bytes:
            with st.spinner("🤖 Analisando imagem com IA (Gemini Vision)..."):
                nutrients = analyze_meal_photo(image_bytes)
        # Análise por texto
        elif description_input:
            with st.spinner("🔍 Buscando informações nutricionais..."):
                nutrients = analyze_meal_by_description(description_input)
        else:
            st.warning("Por favor, tire uma foto, descreva sua refeição ou insira um código de barras.")
            return
        
        # Verifica se houve erro
        if nutrients and 'error' in nutrients:
            st.error(f"❌ {nutrients['error']}")
            
            # Mostra o que foi enviado à API para debug
            if nutrients.get('query_sent'):
                with st.expander("🔍 Ver consulta enviada"):
                    st.code(nutrients['query_sent'], language="text")
            
            st.info("💡 Dica: Tente descrever os alimentos com mais detalhes e quantidades (ex: '100g de frango grelhado, 1 xícara de arroz, salada de alface')")
            return
        
        if nutrients:
            show_analysis_results(nutrients, meal_type, meal_date, location_name)
        else:
            st.error("❌ Não foi possível analisar a refeição. Tente novamente ou descreva manualmente.")

def show_analysis_results(nutrients, meal_type, meal_date, location_name):
    """Exibe resultados da análise e salva no banco."""
    st.success("✅ Análise concluída!")
    
    # Exibe descrição identificada
    if nutrients.get('description'):
        st.info(f"**Descrição:** {nutrients.get('description', 'N/A')}")
    
    # Se houve tradução, mostra o que foi consultado
    if nutrients.get('query_sent') and nutrients.get('query_sent') != nutrients.get('description'):
        with st.expander("🔄 Ver tradução para consulta"):
            st.caption(f"Consulta enviada à API: *{nutrients.get('query_sent')}*")
    
    # Mostra itens encontrados na base de dados
    if nutrients.get('items_detected'):
        st.caption(f"🍽️ Itens encontrados: {', '.join(nutrients.get('items_detected', []))}")
    
    # Cards com nutrientes
    st.markdown("### 📊 Informações Nutricionais")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 Calorias", f"{nutrients.get('calories', 0):.1f} kcal")
    with col2:
        st.metric("🥩 Proteínas", f"{nutrients.get('protein', 0):.1f} g")
    with col3:
        st.metric("🍞 Carboidratos", f"{nutrients.get('carbs', 0):.1f} g")
    with col4:
        st.metric("🧈 Gorduras Totais", f"{nutrients.get('fat_total', 0):.1f} g")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🍬 Açúcares", f"{nutrients.get('sugar', 0):.1f} g")
    with col2:
        st.metric("🥓 Gordura Saturada", f"{nutrients.get('fat_saturated', 0):.1f} g")
    with col3:
        st.metric("🌾 Fibras", f"{nutrients.get('fiber', 0):.1f} g")
    with col4:
        st.metric("🧂 Sódio", f"{nutrients.get('sodium', 0):.1f} mg")
    
    # Salvar automaticamente
    meal = MealData(
        user_id=st.session_state.user_id,
        date=meal_date,
        meal_type=meal_type,
        calories=nutrients.get('calories', 0),
        protein=nutrients.get('protein', 0),
        fat_total=nutrients.get('fat_total', 0),
        fat_saturated=nutrients.get('fat_saturated', 0),
        carbs=nutrients.get('carbs', 0),
        sugar=nutrients.get('sugar', 0),
        fiber=nutrients.get('fiber', 0),
        sodium=nutrients.get('sodium', 0),
        potassium=nutrients.get('potassium', 0),
        cholesterol=nutrients.get('cholesterol', 0),
        description=nutrients.get('description', ''),
        location_name=location_name if location_name else None
    )
    
    meal_id = save_meal(meal)
    st.success(f"💾 Refeição salva com sucesso! (ID: {meal_id})")

    # Limpar formulários das abas após sucesso
    st.divider()
    st.markdown("### 🎉 Refeição salva! Pronto para a próxima?")
    
    if st.button("➕ Analisar outra refeição", use_container_width=True, type="primary"):
        # Limpar os valores dos inputs
        st.session_state.camera = None
        st.session_state.upload = None
        st.session_state.desc_input = ""
        st.session_state.barcode_input = ""
        st.session_state.barcode_quantity = 100
        st.rerun()

def show_daily_summary():
    """Exibe resumo diário de nutrientes."""
    st.markdown("## 📊 Resumo Diário")
    
    selected_date = st.date_input("Selecione a data", value=date.today(), key="summary_date")
    
    macros = get_daily_macros(st.session_state.user_id, selected_date)
    
    st.markdown(f"### Consumo em {selected_date.strftime('%d/%m/%Y')}")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 Calorias", f"{macros.get('calories', 0):.1f} kcal")
    with col2:
        st.metric("🥩 Proteínas", f"{macros.get('protein', 0):.1f} g")
    with col3:
        st.metric("🍞 Carboidratos", f"{macros.get('carbs', 0):.1f} g")
    with col4:
        st.metric("🧈 Gorduras", f"{macros.get('fat_total', 0):.1f} g")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🍬 Açúcares", f"{macros.get('sugar', 0):.1f} g")
    with col2:
        st.metric("🥓 Gord. Saturada", f"{macros.get('fat_saturated', 0):.1f} g")
    with col3:
        st.metric("🌾 Fibras", f"{macros.get('fiber', 0):.1f} g")
    
    # Resumo semanal
    st.divider()
    st.markdown("### 📈 Resumo da Semana")
    
    end_date = date.today()
    start_date = end_date - timedelta(days=7)
    
    weekly_macros = get_aggregated_macros(st.session_state.user_id, start_date, end_date)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Total da semana:**")
        st.write(f"- Calorias: {weekly_macros.get('calories', 0):.1f} kcal")
        st.write(f"- Proteínas: {weekly_macros.get('protein', 0):.1f} g")
        st.write(f"- Carboidratos: {weekly_macros.get('carbs', 0):.1f} g")
    with col2:
        st.markdown("**Média diária:**")
        st.write(f"- Calorias: {weekly_macros.get('calories', 0)/7:.1f} kcal")
        st.write(f"- Proteínas: {weekly_macros.get('protein', 0)/7:.1f} g")
        st.write(f"- Carboidratos: {weekly_macros.get('carbs', 0)/7:.1f} g")

def show_history():
    """Exibe histórico de refeições."""
    st.markdown("## 📈 Histórico de Refeições")
    
    meals = get_user_meals(st.session_state.user_id, limit=100)
    
    if not meals:
        st.info("Nenhuma refeição registrada ainda.")
        return
    
    # Converter para DataFrame
    df = pd.DataFrame(meals)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%d/%m/%Y')
    df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%d/%m/%Y %H:%M')
    
    # Mapear tipos de refeição
    meal_type_map = {
        "breakfast": "☀️ Café da manhã",
        "lunch": "🌤️ Almoço", 
        "dinner": "🌙 Jantar",
        "snack": "🍪 Lanche"
    }
    df['meal_type'] = df['meal_type'].map(meal_type_map)
    
    # Selecionar colunas para exibição
    display_df = df[[
        'date', 'meal_type', 'description', 'calories', 'protein', 
        'carbs', 'fat_total', 'sugar', 'location_name'
    ]].rename(columns={
        'date': 'Data',
        'meal_type': 'Refeição',
        'description': 'Descrição',
        'calories': 'Calorias',
        'protein': 'Proteínas (g)',
        'carbs': 'Carboidratos (g)',
        'fat_total': 'Gorduras (g)',
        'sugar': 'Açúcares (g)',
        'location_name': 'Local'
    })
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Opção de excluir
    st.divider()
    st.markdown("### 🗑️ Excluir Refeição")
    meal_ids = [m['id'] for m in meals]
    meal_options = [f"ID {m['id']} - {m['date']} - {m['description'][:30] if m['description'] else 'Sem descrição'}..." for m in meals]
    
    selected_meal = st.selectbox("Selecione a refeição para excluir", options=range(len(meal_options)), format_func=lambda x: meal_options[x])
    
    if st.button("🗑️ Excluir", type="secondary"):
        if delete_meal(meal_ids[selected_meal], st.session_state.user_id):
            st.success("Refeição excluída com sucesso!")
            st.rerun()
        else:
            st.error("Erro ao excluir refeição.")

def show_backup_page():
    """Página de backup e restore do banco de dados."""
    st.markdown("## 💾 Backup e Restore")
    
    if not BACKUP_AVAILABLE:
        st.error("⚠️ Módulo de backup não disponível.")
        if BACKUP_ERROR:
            st.code(BACKUP_ERROR, language="text")
        st.info("Execute: `pip install -r requirements.txt`")
        return
    
    tab1, tab2, tab3 = st.tabs(["📤 Criar Backup", "📥 Restaurar Backup", "📋 Gerenciar Backups"])
    
    with tab1:
        st.markdown("### Criar novo backup")
        st.info("O backup salva todos os usuários e refeições em um arquivo JSON.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Criar Backup JSON", use_container_width=True, type="primary"):
                with st.spinner("Criando backup..."):
                    try:
                        filepath = export_to_json()
                        st.success(f"✅ Backup criado com sucesso!")
                        st.code(filepath)
                        
                        # Oferecer download
                        with open(filepath, 'r', encoding='utf-8') as f:
                            backup_content = f.read()
                        st.download_button(
                            label="📥 Baixar Backup",
                            data=backup_content,
                            file_name=os.path.basename(filepath),
                            mime="application/json"
                        )
                    except Exception as e:
                        st.error(f"❌ Erro ao criar backup: {str(e)}")
        
        with col2:
            # Baixar arquivo SQLite diretamente
            if os.path.exists(SQLITE_PATH):
                with open(SQLITE_PATH, 'rb') as db_file:
                    db_data = db_file.read()
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                st.download_button(
                    "📥 Baixar Banco SQLite (.db)",
                    data=db_data,
                    file_name=f"caloria_backup_{timestamp}.db",
                    mime="application/octet-stream",
                    use_container_width=True
                )
            else:
                st.warning("⚠️ Arquivo do banco de dados não encontrado.")
    
    with tab2:
        st.markdown("### Restaurar de backup")
        st.warning("⚠️ A restauração pode sobrescrever dados existentes. Faça backup antes!")
        
        # === RESTAURAR BANCO SQLite COMPLETO ===
        st.markdown("#### 📥 Restaurar Banco SQLite (.db)")
        st.info("⚠️ Isso substituirá **completamente** o banco de dados atual!")
        
        uploaded_db = st.file_uploader(
            "Selecione o arquivo .db para restaurar",
            type=['db'],
            key="db_restore_upload"
        )
        
        if uploaded_db is not None:
            st.warning(f"📁 Arquivo selecionado: **{uploaded_db.name}** ({len(uploaded_db.getvalue()) / 1024:.1f} KB)")
            
            confirm_restore = st.checkbox(
                "✅ Confirmo que desejo substituir o banco de dados atual",
                value=False,
                key="confirm_db_restore"
            )
            
            if confirm_restore:
                if st.button("🔄 Restaurar Banco SQLite", type="primary", key="restore_db_btn"):
                    with st.spinner("Restaurando banco de dados..."):
                        try:
                            # Fazer backup do banco atual antes de sobrescrever
                            if os.path.exists(SQLITE_PATH):
                                backup_path = SQLITE_PATH + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                                import shutil
                                shutil.copy2(SQLITE_PATH, backup_path)
                                st.info(f"💾 Backup do banco atual salvo em: {os.path.basename(backup_path)}")
                            
                            # Sobrescrever com o novo arquivo
                            with open(SQLITE_PATH, 'wb') as f:
                                f.write(uploaded_db.getvalue())
                            
                            st.success("✅ Banco de dados restaurado com sucesso!")
                            st.warning("🔄 Por favor, recarregue a página para aplicar as mudanças.")
                            st.balloons()
                        except Exception as e:
                            st.error(f"❌ Erro ao restaurar: {str(e)}")
        
        st.divider()
        
        # === RESTAURAR JSON ===
        st.markdown("#### 📄 Restaurar de backup JSON")
        
        # Upload de arquivo
        uploaded_file = st.file_uploader(
            "Selecione o arquivo de backup JSON",
            type=['json'],
            key="backup_upload"
        )
        
        clear_existing = st.checkbox(
            "Limpar dados existentes antes de importar",
            value=False,
            help="Se marcado, todos os dados serão removidos antes da importação."
        )
        
        if uploaded_file is not None:
            # Mostrar preview
            try:
                content = json.loads(uploaded_file.getvalue().decode('utf-8'))
                st.markdown("**Preview do backup:**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Usuários", content.get('stats', {}).get('total_users', 'N/A'))
                with col2:
                    st.metric("Refeições", content.get('stats', {}).get('total_meals', 'N/A'))
                with col3:
                    backup_date = content.get('backup_date', {})
                    if isinstance(backup_date, dict) and '__datetime__' in backup_date:
                        st.metric("Data", backup_date['__datetime__'][:10])
                    else:
                        st.metric("Data", "N/A")
            except:
                st.error("Não foi possível ler o arquivo.")
            
            if st.button("🔄 Restaurar Backup", type="primary"):
                with st.spinner("Restaurando..."):
                    try:
                        # Salvar arquivo temporário
                        temp_path = f"/tmp/restore_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
                        with open(temp_path, 'wb') as f:
                            f.write(uploaded_file.getvalue())
                        
                        # Importar
                        stats = import_from_json(temp_path, clear_existing=clear_existing)
                        
                        # Remover arquivo temporário
                        os.remove(temp_path)
                        
                        st.success("✅ Restauração concluída!")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Usuários importados", stats['users_imported'])
                            st.metric("Usuários ignorados", stats['users_skipped'])
                        with col2:
                            st.metric("Refeições importadas", stats['meals_imported'])
                            st.metric("Refeições ignoradas", stats['meals_skipped'])
                        
                        if stats['errors']:
                            st.warning(f"⚠️ {len(stats['errors'])} erros durante importação")
                            with st.expander("Ver erros"):
                                for err in stats['errors']:
                                    st.text(err)
                    except Exception as e:
                        st.error(f"❌ Erro na restauração: {str(e)}")
    
    with tab3:
        st.markdown("### Backups salvos")
        
        backups = list_backups()
        
        if not backups:
            st.info("Nenhum backup encontrado na pasta de backups.")
        else:
            for backup in backups:
                with st.expander(f"📁 {backup['filename']} ({backup['size_mb']} MB)"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Criado em:** {backup['created'].strftime('%d/%m/%Y %H:%M')}")
                    with col2:
                        st.write(f"**Usuários:** {backup['total_users']}")
                    with col3:
                        st.write(f"**Refeições:** {backup['total_meals']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        # Download
                        with open(backup['filepath'], 'r', encoding='utf-8') as f:
                            st.download_button(
                                "📥 Download",
                                data=f.read(),
                                file_name=backup['filename'],
                                mime="application/json",
                                key=f"dl_{backup['filename']}"
                            )
                    with col2:
                        # Restaurar
                        if st.button("🔄 Restaurar", key=f"restore_{backup['filename']}"):
                            try:
                                stats = import_from_json(backup['filepath'])
                                st.success(f"Restaurado! {stats['users_imported']} usuários, {stats['meals_imported']} refeições")
                            except Exception as e:
                                st.error(f"Erro: {str(e)}")
                    with col3:
                        # Excluir
                        if st.button("🗑️ Excluir", key=f"del_{backup['filename']}"):
                            if delete_backup(backup['filepath']):
                                st.success("Backup excluído!")
                                st.rerun()
                            else:
                                st.error("Erro ao excluir.")

def show_reports_page():
    """Página de geração de relatórios PDF."""
    st.markdown("## 📄 Relatórios Nutricionais")
    
    if not REPORTS_AVAILABLE:
        st.error("⚠️ Módulo de relatórios não disponível.")
        if REPORTS_ERROR:
            st.code(REPORTS_ERROR, language="text")
        st.info("Execute: `pip install reportlab`")
        return
    
    st.info("🤖 Os relatórios incluem análise nutricional gerada por IA (Perplexity) com recomendações personalizadas.")
    
    # Configurações do relatório
    col1, col2 = st.columns(2)
    
    with col1:
        period = st.selectbox(
            "Período do relatório",
            ["day", "week", "month", "year"],
            format_func=lambda x: {
                "day": "📅 Diário",
                "week": "📆 Semanal",
                "month": "🗓️ Mensal",
                "year": "📊 Anual"
            }.get(x, x),
            index=1,
            key="report_period"
        )
    
    with col2:
        reference_date = st.date_input(
            "Data de referência",
            value=date.today(),
            key="report_date"
        )
    
    # Mostrar período selecionado
    start_date, end_date = get_period_dates(period, reference_date)
    st.markdown(f"**Período selecionado:** {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}")
    
    st.divider()
    
    # Opções do relatório
    include_ai = st.checkbox(
        "🤖 Incluir análise de IA",
        value=True,
        help="Gera uma análise nutricional personalizada usando Perplexity AI"
    )
    
    st.divider()
    
    # Botão de geração
    if st.button("📄 Gerar Relatório PDF", type="primary", use_container_width=True):
        with st.spinner("📝 Gerando relatório... Isso pode levar alguns segundos."):
            try:
                # Gerar PDF
                pdf_bytes = generate_pdf_report(
                    user_id=st.session_state.user_id,
                    period=period,
                    reference_date=reference_date,
                    include_ai_analysis=include_ai
                )
                
                # Nome do arquivo
                filename = get_report_filename(period, start_date, end_date)
                
                st.success("✅ Relatório gerado com sucesso!")
                
                # Botão de download
                st.download_button(
                    label="📥 Baixar Relatório PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )
                
            except Exception as e:
                st.error(f"❌ Erro ao gerar relatório: {str(e)}")
                import traceback
                st.code(traceback.format_exc())
    
    st.divider()
    
    # Preview rápido dos dados
    st.markdown("### 👁️ Preview dos Dados")
    
    macros = get_aggregated_macros(st.session_state.user_id, start_date, end_date)
    days = (end_date - start_date).days + 1
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔥 Calorias Total", f"{macros.get('calories', 0):.0f} kcal")
        st.metric("🔥 Média/dia", f"{macros.get('calories', 0)/days:.0f} kcal")
    with col2:
        st.metric("🥩 Proteínas Total", f"{macros.get('protein', 0):.1f}g")
        st.metric("🥩 Média/dia", f"{macros.get('protein', 0)/days:.1f}g")
    with col3:
        st.metric("🍞 Carboidratos Total", f"{macros.get('carbs', 0):.1f}g")
        st.metric("🍞 Média/dia", f"{macros.get('carbs', 0)/days:.1f}g")
    with col4:
        st.metric("🧈 Gorduras Total", f"{macros.get('fat_total', 0):.1f}g")
        st.metric("🧈 Média/dia", f"{macros.get('fat_total', 0)/days:.1f}g")


def show_profile_page():
    """Página de gestão do perfil do usuário."""
    st.markdown("## 👤 Meu Perfil")
    
    # Carregar dados do usuário
    user_data = get_user_by_id(st.session_state.user_id)
    if not user_data:
        st.error("Erro ao carregar dados do usuário.")
        return
    
    tab1, tab2, tab3 = st.tabs(["📋 Dados Pessoais", "🎯 Metas Nutricionais", "🔐 Segurança"])
    
    # === ABA 1: DADOS PESSOAIS ===
    with tab1:
        st.markdown("### Informações Pessoais")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Peso
            current_weight = user_data.get('weight') or 0.0
            new_weight = st.number_input(
                "⚖️ Peso (kg)",
                min_value=0.0,
                max_value=300.0,
                value=float(current_weight),
                step=0.1,
                format="%.1f"
            )
            
            # Altura
            current_height = user_data.get('height') or 0.0
            new_height = st.number_input(
                "📏 Altura (m)",
                min_value=0.0,
                max_value=2.5,
                value=float(current_height),
                step=0.01,
                format="%.2f"
            )
        
        with col2:
            # Data de nascimento
            current_birth = user_data.get('birth_date')
            if current_birth:
                default_birth = current_birth
            else:
                default_birth = date(1990, 1, 1)
            
            new_birth_date = st.date_input(
                "🎂 Data de Nascimento",
                value=default_birth,
                min_value=date(1920, 1, 1),
                max_value=date.today()
            )
            
            # Calcular e mostrar idade
            if new_birth_date:
                today = date.today()
                age = today.year - new_birth_date.year - ((today.month, today.day) < (new_birth_date.month, new_birth_date.day))
                st.info(f"📅 Idade: **{age} anos**")
        
        # Calcular e mostrar IMC
        if new_weight > 0 and new_height > 0:
            imc = new_weight / (new_height ** 2)
            if imc < 18.5:
                imc_status = "Abaixo do peso"
                imc_color = "🔵"
            elif imc < 25:
                imc_status = "Peso normal"
                imc_color = "🟢"
            elif imc < 30:
                imc_status = "Sobrepeso"
                imc_color = "🟡"
            else:
                imc_status = "Obesidade"
                imc_color = "🔴"
            
            st.metric(f"{imc_color} IMC", f"{imc:.1f}", imc_status)
        
        if st.button("💾 Salvar Dados Pessoais", use_container_width=True, type="primary"):
            success = update_user_profile(
                st.session_state.user_id,
                weight=new_weight if new_weight > 0 else None,
                height=new_height if new_height > 0 else None,
                birth_date=new_birth_date
            )
            if success:
                st.success("✅ Dados pessoais atualizados com sucesso!")
            else:
                st.error("❌ Erro ao atualizar dados.")
    
    # === ABA 2: METAS NUTRICIONAIS ===
    with tab2:
        st.markdown("### Metas Diárias")
        
        # Calorias
        current_cal = user_data.get('cal_limit') or 2000.0
        new_cal_limit = st.number_input(
            "🔥 Meta de Calorias (kcal/dia)",
            min_value=500,
            max_value=10000,
            value=int(current_cal),
            step=50
        )
        
        st.divider()
        st.markdown("### Distribuição de Macronutrientes (%)")
        st.caption("Os percentuais devem somar 100%")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            current_protein_pct = user_data.get('protein_pct') or 30.0
            new_protein_pct = st.slider(
                "🥩 Proteína (%)",
                min_value=10,
                max_value=60,
                value=int(current_protein_pct),
                step=5
            )
        
        with col2:
            current_fat_pct = user_data.get('fat_pct') or 25.0
            new_fat_pct = st.slider(
                "🧈 Gordura (%)",
                min_value=10,
                max_value=60,
                value=int(current_fat_pct),
                step=5
            )
        
        with col3:
            current_carbs_pct = user_data.get('carbs_pct') or 45.0
            new_carbs_pct = st.slider(
                "🍞 Carboidrato (%)",
                min_value=10,
                max_value=70,
                value=int(current_carbs_pct),
                step=5
            )
        
        # Validar soma
        total_pct = new_protein_pct + new_fat_pct + new_carbs_pct
        if total_pct != 100:
            st.warning(f"⚠️ Total: {total_pct}% - Deve somar 100%")
        else:
            st.success(f"✅ Total: {total_pct}%")
        
        # Calcular gramas baseado nas calorias e percentuais
        st.divider()
        st.markdown("### Metas em Gramas (calculadas automaticamente)")
        
        # Proteína: 4 kcal/g, Carbs: 4 kcal/g, Gordura: 9 kcal/g
        protein_grams = (new_cal_limit * new_protein_pct / 100) / 4
        carbs_grams = (new_cal_limit * new_carbs_pct / 100) / 4
        fat_grams = (new_cal_limit * new_fat_pct / 100) / 9
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🥩 Proteína", f"{protein_grams:.0f}g/dia")
        with col2:
            st.metric("🧈 Gordura", f"{fat_grams:.0f}g/dia")
        with col3:
            st.metric("🍞 Carboidrato", f"{carbs_grams:.0f}g/dia")
        
        if st.button("💾 Salvar Metas Nutricionais", use_container_width=True, type="primary"):
            if total_pct != 100:
                st.error("❌ Os percentuais devem somar 100%!")
            else:
                success = update_user_profile(
                    st.session_state.user_id,
                    cal_limit=float(new_cal_limit),
                    protein_pct=float(new_protein_pct),
                    fat_pct=float(new_fat_pct),
                    carbs_pct=float(new_carbs_pct),
                    protein_limit=protein_grams,
                    fat_limit=fat_grams,
                    carbs_limit=carbs_grams
                )
                if success:
                    st.success("✅ Metas nutricionais atualizadas com sucesso!")
                else:
                    st.error("❌ Erro ao atualizar metas.")
    
    # === ABA 3: SEGURANÇA ===
    with tab3:
        st.markdown("### Alterar Senha")
        
        with st.form("change_password_form"):
            current_password = st.text_input("Senha Atual", type="password")
            new_password = st.text_input("Nova Senha", type="password")
            confirm_password = st.text_input("Confirmar Nova Senha", type="password")
            
            submitted = st.form_submit_button("🔐 Alterar Senha", use_container_width=True)
            
            if submitted:
                if not current_password or not new_password or not confirm_password:
                    st.error("❌ Preencha todos os campos.")
                elif new_password != confirm_password:
                    st.error("❌ As senhas não coincidem.")
                elif len(new_password) < 4:
                    st.error("❌ A nova senha deve ter pelo menos 4 caracteres.")
                else:
                    # Verificar senha atual
                    user = get_user_by_username(st.session_state.username)
                    if user and verify_password_hash(current_password, user['password_hash']):
                        # Atualizar senha
                        new_hash = create_password_hash(new_password)
                        success = update_user_password(st.session_state.user_id, new_hash)
                        if success:
                            st.success("✅ Senha alterada com sucesso!")
                        else:
                            st.error("❌ Erro ao atualizar senha.")
                    else:
                        st.error("❌ Senha atual incorreta.")
        
        st.divider()
        st.markdown("### Informações da Conta")
        st.info(f"👤 **Usuário:** {st.session_state.username}")
        st.info(f"🆔 **ID:** {st.session_state.user_id}")


# Main app
def main():
    init_session_state()
    
    if not st.session_state.logged_in:
        show_login_page()
    else:
        page = show_sidebar()
        
        if page == "🍽️ Nova Análise":
            show_analysis_page()
        elif page == "📊 Resumo Diário":
            show_daily_summary()
        elif page == "📈 Histórico":
            show_history()
        # Mapa de Refeições removido
        elif page == "📄 Relatórios":
            show_reports_page()
        elif page == "👤 Meu Perfil":
            show_profile_page()
        elif page == "💾 Backup/Restore":
            show_backup_page()

if __name__ == "__main__":
    main()
