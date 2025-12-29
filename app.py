import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from auth import generate_token, decode_token, create_password_hash, verify_password_hash
from api_perplexity import analyze_meal_by_description, analyze_meal_by_barcode, analyze_meal_photo
from nutrition_fixes import safe_session_key, process_gemini_food_items
from models import MealData
from storage import (
    save_meal,
    get_daily_macros,
    get_aggregated_macros,
    create_user,
    get_user_by_username,
    get_user_by_id,
    update_user_profile,
    update_user_password,
    get_user_meals,
    delete_meal
)
from db import init_db, SQLITE_PATH
import json
import os

# Importações opcionais com fallback (para evitar erro se reportlab não estiver instalado)
BACKUP_AVAILABLE = False
BACKUP_ERROR = None
try:
    from backup import (
        export_to_json,
        import_from_json,
        list_backups,
        delete_backup,
        mysql_dump,
        mysql_restore,
        quick_backup
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
    .main { padding: 20px; }
    .metric-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; }
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
    if 'reset_form' not in st.session_state:
        st.session_state.reset_form = False

def show_login_page():
    """Exibe página de login/cadastro."""
    st.markdown('# 🍽️ Caloria - Análise Nutricional Inteligente', unsafe_allow_html=True)
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
                        new_username,
                        pwd_hash,
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
            ["🍽️ Nova Análise", "📊 Resumo Diário", "📈 Histórico", "📄 Relatórios", "👤 Meu Perfil", "💾 Backup/Restore", "⚙️ Configurações"],
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

            # Status Gemini
            gemini_key = os.getenv('GEMINI_KEY') or os.getenv('GEMINI_API_KEY')
            if gemini_key:
                st.success("✅ Gemini Vision (Leitura de Fotos)")
            else:
                st.error("❌ Gemini Vision")

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
    """Componente para capturar localização."""
    st.markdown("#### 📍 Localização")

    # Buscar locais já cadastrados
    location_options = []
    try:
        user_id = st.session_state.get('user_id', None)
        if user_id:
            meals = get_user_meals(user_id, limit=200)
            location_options = sorted(list(set([m['location_name'] for m in meals if m['location_name']])))
    except Exception as e:
        location_options = []

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

    if st.session_state.reset_form:
        st.session_state.reset_form = False
        st.session_state.desc_input = ""
        st.session_state.barcode_input = ""
        st.session_state.barcode_quantity = 100

    tab1, tab2, tab3 = st.tabs(["📷 Tirar Foto", "✍️ Descrever Refeição", "📊 Código de Barras"])

    with tab1:
        st.markdown("### 📷 Análise por Foto")
        st.info("💡 Tire uma foto do seu prato ou do rótulo nutricional de um produto.")
        img_file = st.camera_input("Capturar foto", key="camera")
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
        st.info("💡 Seja específico com as quantidades para uma análise mais precisa.")
        description_input = st.text_area(
            "O que você comeu?",
            placeholder="Ex: 1 prato de arroz, 100g de frango grelhado, salada de alface com tomate",
            height=120,
            key="desc_input",
            value=st.session_state.desc_input
        )

    with tab3:
        st.markdown("### 📊 Buscar por Código de Barras")
        barcode_input = st.text_input(
            "Código de barras",
            placeholder="Ex: 7894900011517",
            key="barcode_input",
            value=st.session_state.barcode_input
        )
        barcode_quantity = st.number_input(
            "Quantidade consumida (gramas ou ml)",
            min_value=1,
            max_value=5000,
            value=st.session_state.get('barcode_quantity', 100),
            step=10,
            key="barcode_quantity"
        )

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        meal_type = st.selectbox(
            "Tipo de refeição",
            ["breakfast", "lunch", "dinner", "snack"],
            index=1,
            format_func=lambda x: {"breakfast": "☀️ Café da manhã", "lunch": "🌤️ Almoço", "dinner": "🌙 Jantar", "snack": "🍪 Lanche"}.get(x, x),
            key="meal_type"
        )
    with col2:
        meal_date = st.date_input("Data", value=date.today(), key="meal_date")

    st.divider()
    location_name = get_location_component()
    st.divider()

    if st.button("🔍 Analisar Refeição", use_container_width=True, type="primary"):
        nutrients = None

        if barcode_input and barcode_input.strip():
            with st.spinner("📊 Buscando produto no Open Food Facts..."):
                nutrients = analyze_meal_by_barcode(barcode_input.strip(), quantity_grams=float(barcode_quantity))
        elif image_bytes:
            with st.spinner("🤖 Analisando imagem com IA (Gemini Vision)..."):
                nutrients = analyze_meal_photo(image_bytes)
        elif description_input:
            with st.spinner("🔍 Buscando informações nutricionais..."):
                nutrients = analyze_meal_by_description(description_input)
        else:
            st.warning("Por favor, tire uma foto, descreva sua refeição ou insira um código de barras.")
            return

        if nutrients and 'error' in nutrients:
            st.error(f"❌ {nutrients['error']}")
            if nutrients.get('query_sent'):
                with st.expander("🔍 Ver consulta enviada"):
                    st.code(nutrients['query_sent'], language="text")
            st.info("💡 Tente descrever os alimentos com mais detalhes e quantidades.")
            return

        if nutrients:
            show_analysis_results(nutrients, meal_type, meal_date, location_name)
        else:
            st.error("❌ Não foi possível analisar a refeição. Tente novamente.")

def show_analysis_results(nutrients, meal_type, meal_date, location_name):
    """Exibe resultados e salva no banco."""
    st.success("✅ Análise concluída!")

    if nutrients.get('description'):
        st.info(f"**Descrição:** {nutrients.get('description', 'N/A')}")

    if nutrients.get('items_detected'):
        st.caption(f"🍽️ Itens encontrados: {', '.join(nutrients.get('items_detected', []))}")

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

    # SALVAR NO BANCO - ISSO ERA O PROBLEMA!
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

    st.divider()
    st.markdown("### 🎉 Refeição salva! Pronto para a próxima?")
    if st.button("➕ Analisar outra refeição", use_container_width=True, type="primary"):
        st.session_state.reset_form = True
        st.session_state.desc_input = ""
        st.session_state.barcode_input = ""
        st.session_state.barcode_quantity = 100
        st.rerun()

def show_daily_summary():
    """Exibe resumo diário."""
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
        st.write(f"- Gorduras: {weekly_macros.get('fat_total', 0):.1f} g")

    with col2:
        st.markdown("**Média diária:**")
        st.write(f"- Calorias: {weekly_macros.get('calories', 0)/7:.1f} kcal")
        st.write(f"- Proteínas: {weekly_macros.get('protein', 0)/7:.1f} g")
        st.write(f"- Carboidratos: {weekly_macros.get('carbs', 0)/7:.1f} g")
        st.write(f"- Gorduras: {weekly_macros.get('fat_total', 0)/7:.1f} g")

def show_history_page():
    """Exibe histórico de refeições."""
    st.markdown("## 📈 Histórico")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Data inicial", value=date.today() - timedelta(days=30), key="hist_start")
    with col2:
        end_date = st.date_input("Data final", value=date.today(), key="hist_end")

    meals = get_user_meals(st.session_state.user_id, limit=500)
    meals_filtered = [m for m in meals if start_date <= m['date'] <= end_date]

    if not meals_filtered:
        st.info("Nenhuma refeição registrada no período.")
        return

    # Converter para DataFrame
    df = pd.DataFrame(meals_filtered)
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%d/%m/%Y')
    df['meal_type'] = df['meal_type'].map({"breakfast": "☀️ Café", "lunch": "🌤️ Almoço", "dinner": "🌙 Jantar", "snack": "🍪 Lanche"})

    st.dataframe(df[['date', 'meal_type', 'description', 'calories', 'protein', 'carbs', 'fat_total']].sort_values('date', ascending=False), use_container_width=True)

    # Estatísticas
    st.divider()
    st.markdown("### 📊 Estatísticas do Período")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de refeições", len(meals_filtered))
    with col2:
        st.metric("Calorias totais", f"{sum(m['calories'] for m in meals_filtered):.0f}")
    with col3:
        st.metric("Proteína total", f"{sum(m['protein'] for m in meals_filtered):.1f}g")
    with col4:
        st.metric("Carboidrato total", f"{sum(m['carbs'] for m in meals_filtered):.1f}g")

def show_reports_page():
    """Página de relatórios."""
    st.markdown("## 📄 Relatórios Nutricionais")

    if not REPORTS_AVAILABLE:
        st.error("⚠️ Módulo de relatórios não disponível.")
        if REPORTS_ERROR:
            st.code(REPORTS_ERROR, language="text")
        st.info("Execute: `pip install reportlab`")
        return

    st.info("🤖 Os relatórios incluem análise nutricional gerada por IA (Perplexity).")

    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox(
            "Período do relatório",
            ["day", "week", "month", "year"],
            format_func=lambda x: {"day": "📅 Diário", "week": "📆 Semanal", "month": "🗓️ Mensal", "year": "📊 Anual"}.get(x, x),
            index=1,
            key="report_period"
        )
    with col2:
        reference_date = st.date_input("Data de referência", value=date.today(), key="report_date")

    start_date, end_date = get_period_dates(period, reference_date)
    st.markdown(f"**Período selecionado:** {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}")

    st.divider()
    include_ai = st.checkbox("🤖 Incluir análise de IA", value=True)
    st.divider()

    if st.button("📄 Gerar Relatório PDF", type="primary", use_container_width=True):
        with st.spinner("📝 Gerando relatório..."):
            try:
                pdf_bytes = generate_pdf_report(
                    user_id=st.session_state.user_id,
                    period=period,
                    reference_date=reference_date,
                    include_ai_analysis=include_ai
                )
                filename = get_report_filename(period, start_date, end_date)
                st.success("✅ Relatório gerado com sucesso!")
                st.download_button(
                    label="📥 Baixar Relatório PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"❌ Erro ao gerar relatório: {str(e)}")

    st.divider()
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
    """Página de perfil do usuário."""
    st.markdown("## 👤 Meu Perfil")

    user_data = get_user_by_id(st.session_state.user_id)
    if not user_data:
        st.error("Erro ao carregar dados do usuário.")
        return

    tab1, tab2, tab3 = st.tabs(["📋 Dados Pessoais", "🎯 Metas Nutricionais", "🔐 Segurança"])

    with tab1:
        st.markdown("### Informações Pessoais")
        col1, col2 = st.columns(2)
        with col1:
            current_weight = user_data.get('weight') or 0.0
            new_weight = st.number_input("⚖️ Peso (kg)", min_value=0.0, max_value=300.0, value=float(current_weight), step=0.1, format="%.1f")

            current_height = user_data.get('height') or 0.0
            new_height = st.number_input("📏 Altura (m)", min_value=0.0, max_value=2.5, value=float(current_height), step=0.01, format="%.2f")

        with col2:
            current_birth = user_data.get('birth_date')
            if current_birth:
                default_birth = current_birth
            else:
                default_birth = date(1990, 1, 1)
            new_birth_date = st.date_input("🎂 Data de Nascimento", value=default_birth, min_value=date(1920, 1, 1), max_value=date.today())

            if new_birth_date:
                today = date.today()
                age = today.year - new_birth_date.year - ((today.month, today.day) < (new_birth_date.month, new_birth_date.day))
                st.info(f"📅 Idade: **{age} anos**")

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

    with tab2:
        st.markdown("### Metas Diárias")
        current_cal = user_data.get('cal_limit') or 2000.0
        new_cal_limit = st.number_input("🔥 Meta de Calorias (kcal/dia)", min_value=500, max_value=10000, value=int(current_cal), step=50)

        st.divider()
        st.markdown("### Distribuição de Macronutrientes (%)")
        st.caption("Os percentuais devem somar 100%")
        col1, col2, col3 = st.columns(3)
        with col1:
            current_protein_pct = user_data.get('protein_pct') or 30.0
            new_protein_pct = st.slider("🥩 Proteína (%)", min_value=10, max_value=60, value=int(current_protein_pct), step=5)
        with col2:
            current_fat_pct = user_data.get('fat_pct') or 25.0
            new_fat_pct = st.slider("🧈 Gordura (%)", min_value=10, max_value=60, value=int(current_fat_pct), step=5)
        with col3:
            current_carbs_pct = user_data.get('carbs_pct') or 45.0
            new_carbs_pct = st.slider("🍞 Carboidrato (%)", min_value=10, max_value=70, value=int(current_carbs_pct), step=5)

        total_pct = new_protein_pct + new_fat_pct + new_carbs_pct
        if total_pct != 100:
            st.warning(f"⚠️ Total: {total_pct}% - Deve somar 100%")
        else:
            st.success(f"✅ Total: {total_pct}%")

        # Calcular gramas
        protein_grams = (new_cal_limit * new_protein_pct / 100) / 4
        fat_grams = (new_cal_limit * new_fat_pct / 100) / 9
        carbs_grams = (new_cal_limit * new_carbs_pct / 100) / 4
        st.caption(f"🥩 {protein_grams:.0f}g | 🧈 {fat_grams:.0f}g | 🍞 {carbs_grams:.0f}g")

        if st.button("💾 Salvar Metas", use_container_width=True, type="primary"):
            if total_pct == 100:
                success = update_user_profile(
                    st.session_state.user_id,
                    cal_limit=float(new_cal_limit),
                    protein_limit=protein_grams,
                    fat_limit=fat_grams,
                    carbs_limit=carbs_grams,
                    protein_pct=float(new_protein_pct),
                    fat_pct=float(new_fat_pct),
                    carbs_pct=float(new_carbs_pct)
                )
                if success:
                    st.success("✅ Metas atualizadas com sucesso!")
                else:
                    st.error("❌ Erro ao atualizar metas.")
            else:
                st.error("Os percentuais devem somar 100%.")

    with tab3:
        st.markdown("### Alterar Senha")
        current_password = st.text_input("Senha atual", type="password", key="current_pass")
        new_password = st.text_input("Nova senha", type="password", key="new_pass")
        confirm_password = st.text_input("Confirmar nova senha", type="password", key="confirm_pass")

        if st.button("🔐 Alterar Senha", use_container_width=True, type="primary"):
            if not verify_password_hash(user_data['password_hash'], current_password):
                st.error("❌ Senha atual incorreta.")
            elif new_password != confirm_password:
                st.error("❌ As senhas não coincidem.")
            elif len(new_password) < 6:
                st.error("❌ A nova senha deve ter pelo menos 6 caracteres.")
            else:
                new_hash = create_password_hash(new_password)
                if update_user_password(st.session_state.user_id, new_hash):
                    st.success("✅ Senha alterada com sucesso!")
                else:
                    st.error("❌ Erro ao alterar senha.")

def show_backup_page():
    """Página de backup e restore."""
    st.markdown("## 💾 Backup / Restore")

    if not BACKUP_AVAILABLE:
        st.error("⚠️ Módulo de backup não disponível.")
        if BACKUP_ERROR:
            st.code(BACKUP_ERROR, language="text")
        return

    tab1, tab2 = st.tabs(["📥 Criar Backup", "📤 Restaurar"])

    with tab1:
        st.markdown("### 📥 Novo Backup")
        if st.button("🔄 Fazer Backup Agora", type="primary", use_container_width=True):
            with st.spinner("Criando backup..."):
                try:
                    filepath = quick_backup()
                    st.success(f"✅ Backup criado: {filepath}")
                except Exception as e:
                    st.error(f"❌ Erro ao criar backup: {str(e)}")

    with tab2:
        st.markdown("### 📤 Restaurar Backup")
        backups = list_backups()

        if not backups:
            st.info("Nenhum backup disponível.")
            return

        for backup in backups:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"📅 {backup['created'].strftime('%d/%m/%Y %H:%M')}")
            with col2:
                st.write(f"**Usuários:** {backup['total_users']}")
            with col3:
                st.write(f"**Refeições:** {backup['total_meals']}")

            col1, col2, col3 = st.columns(3)
            with col1:
                with open(backup['filepath'], 'r', encoding='utf-8') as f:
                    st.download_button("📥 Download", data=f.read(), file_name=backup['filename'], mime="application/json", key=f"dl_{backup['filename']}")
            with col2:
                if st.button("🔄 Restaurar", key=f"restore_{backup['filename']}"):
                    try:
                        stats = import_from_json(backup['filepath'])
                        st.success(f"Restaurado! {stats['users_imported']} usuários, {stats['meals_imported']} refeições")
                    except Exception as e:
                        st.error(f"Erro: {str(e)}")
            with col3:
                if st.button("🗑️ Excluir", key=f"del_{backup['filename']}"):
                    if delete_backup(backup['filepath']):
                        st.success("Backup excluído!")
                        st.rerun()
                    else:
                        st.error("Erro ao excluir.")

def show_settings_page():
    """Página de configurações."""
    st.markdown("## ⚙️ Configurações")

    tab1, tab2 = st.tabs(["📊 Sistema", "💾 Backup"])

    with tab1:
        st.markdown("### Status do Sistema")
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**APIs Configuradas:**")
            perplexity_key = os.getenv('PERPLEXITY_API_KEY')
            if perplexity_key:
                st.success("✅ Perplexity API")
            else:
                st.error("❌ Perplexity API")

            gemini_key = os.getenv('GEMINI_KEY') or os.getenv('GEMINI_API_KEY')
            if gemini_key:
                st.success("✅ Gemini Vision")
            else:
                st.error("❌ Gemini Vision")

        with col2:
            st.markdown("**Módulos:**")
            if BACKUP_AVAILABLE:
                st.success("✅ Backup")
            else:
                st.error("❌ Backup")

            if REPORTS_AVAILABLE:
                st.success("✅ Relatórios")
            else:
                st.error("❌ Relatórios")

        st.divider()
        st.markdown("### Versão do Banco de Dados")
        st.info(f"📍 Local: {SQLITE_PATH}")

    with tab2:
        st.markdown("### 💾 Gerenciamento de Backup")
        st.info("Crie backups automáticos dos seus dados.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Criar Novo Backup", type="primary", use_container_width=True):
                with st.spinner("Criando backup..."):
                    try:
                        filepath = quick_backup()
                        st.success(f"✅ Backup criado com sucesso!")
                        st.info(f"📍 Local: {filepath}")
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")

        with col2:
            if st.button("📤 Ver Backups", use_container_width=True):
                backups = list_backups()
                if backups:
                    st.success(f"✅ {len(backups)} backup(s) encontrado(s)")
                    for backup in backups[:5]:  # Mostrar últimos 5
                        st.caption(f"📅 {backup['created'].strftime('%d/%m/%Y %H:%M')} - {backup['size_mb']} MB")
                else:
                    st.info("Nenhum backup disponível")

# Main
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
        show_history_page()
    elif page == "📄 Relatórios":
        show_reports_page()
    elif page == "👤 Meu Perfil":
        show_profile_page()
    elif page == "💾 Backup/Restore":
        show_backup_page()
    elif page == "⚙️ Configurações":
        show_settings_page()
