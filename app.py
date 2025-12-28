import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from auth import generate_token, decode_token, create_password_hash, verify_password_hash
from api_perplexity import analyze_meal_photo, analyze_meal_by_description
from models import MealData
from storage import (
    save_meal, get_daily_macros, get_aggregated_macros, create_user,
    get_user_by_username, get_user_meals, get_meals_with_location, delete_meal
)
from db import init_db
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
    """Inicializa variáveis de sessão."""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'current_location' not in st.session_state:
        st.session_state.current_location = None

def show_login_page():
    """Exibe página de login/cadastro."""
    st.markdown('<h1 class="main-header">🍽️ Caloria</h1>', unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Análise nutricional inteligente por foto</p>", unsafe_allow_html=True)
    
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
            st.subheader("Dados físicos (opcional)")
            col1, col2 = st.columns(2)
            with col1:
                weight = st.number_input("Peso (kg)", min_value=0.0, max_value=500.0, format="%.1f", key="reg_weight")
                height = st.number_input("Altura (m)", min_value=0.0, max_value=3.0, format="%.2f", key="reg_height")
            
            st.divider()
            st.subheader("Limites diários (opcional)")
            col1, col2, col3 = st.columns(3)
            with col1:
                cal_limit = st.number_input("Calorias", min_value=0.0, value=2000.0, key="reg_cal")
                protein_limit = st.number_input("Proteínas (g)", min_value=0.0, value=50.0, key="reg_prot")
            with col2:
                fat_limit = st.number_input("Gorduras (g)", min_value=0.0, value=65.0, key="reg_fat")
                carbs_limit = st.number_input("Carboidratos (g)", min_value=0.0, value=300.0, key="reg_carbs")
            with col3:
                sugar_limit = st.number_input("Açúcares (g)", min_value=0.0, value=50.0, key="reg_sugar")
            
            submit = st.form_submit_button("Cadastrar", use_container_width=True)
            
            if submit:
                if not new_username or not new_password:
                    st.error("Preencha usuário e senha.")
                elif new_password != confirm_password:
                    st.error("As senhas não coincidem.")
                elif get_user_by_username(new_username):
                    st.error("Este usuário já existe.")
                else:
                    pwd_hash = create_password_hash(new_password)
                    user_id = create_user(
                        new_username, pwd_hash, weight or None, height or None,
                        cal_limit or None, protein_limit or None, fat_limit or None,
                        carbs_limit or None, sugar_limit or None
                    )
                    st.success("Conta criada com sucesso! Faça login.")

def show_sidebar():
    """Exibe sidebar com navegação."""
    with st.sidebar:
        st.markdown(f"### 👋 Olá, {st.session_state.username}!")
        st.divider()
        
        page = st.radio(
            "Navegação",
            ["📸 Nova Análise", "📊 Resumo Diário", "📈 Histórico", "🗺️ Mapa de Refeições", "📄 Relatórios", "💾 Backup/Restore"],
            label_visibility="collapsed"
        )
        
        st.divider()
        
        # Status das APIs
        with st.expander("🔧 Status do Sistema", expanded=False):
            perplexity_key = os.getenv('PERPLEXITY_API_KEY')
            calorieninjas_key = os.getenv('CALORIENINJAS_API_KEY')
            
            if perplexity_key:
                st.success("✅ Perplexity API")
            else:
                st.error("❌ Perplexity API")
            
            if calorieninjas_key:
                st.success("✅ CalorieNinjas API")
            else:
                st.error("❌ CalorieNinjas API")
            
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
    
    # JavaScript para obter localização do navegador
    location_js = """
    <script>
    function getLocation() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    // Envia para o Streamlit via query params
                    const url = new URL(window.location.href);
                    url.searchParams.set('auto_lat', lat.toFixed(6));
                    url.searchParams.set('auto_lon', lon.toFixed(6));
                    document.getElementById('geo_status').innerHTML = '✅ Localização obtida: ' + lat.toFixed(4) + ', ' + lon.toFixed(4);
                    // Salva no sessionStorage para persistência
                    sessionStorage.setItem('geo_lat', lat);
                    sessionStorage.setItem('geo_lon', lon);
                },
                function(error) {
                    document.getElementById('geo_status').innerHTML = '❌ Erro: ' + error.message;
                },
                {enableHighAccuracy: true, timeout: 10000}
            );
        } else {
            document.getElementById('geo_status').innerHTML = '❌ Geolocalização não suportada';
        }
    }
    
    // Tenta recuperar do sessionStorage
    window.onload = function() {
        const savedLat = sessionStorage.getItem('geo_lat');
        const savedLon = sessionStorage.getItem('geo_lon');
        if (savedLat && savedLon) {
            document.getElementById('geo_status').innerHTML = '📍 Usando localização salva: ' + parseFloat(savedLat).toFixed(4) + ', ' + parseFloat(savedLon).toFixed(4);
        }
    }
    </script>
    <button onclick="getLocation()" style="padding: 8px 16px; background-color: #2E7D32; color: white; border: none; border-radius: 5px; cursor: pointer; margin-bottom: 10px;">
        📍 Obter Localização Automática
    </button>
    <div id="geo_status" style="font-size: 12px; color: #666; margin-bottom: 10px;"></div>
    """
    
    st.components.v1.html(location_js, height=80)
    
    # Campos manuais
    st.caption("Ou insira manualmente:")
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("Latitude", value=0.0, format="%.6f", key="lat_input")
    with col2:
        lon = st.number_input("Longitude", value=0.0, format="%.6f", key="lon_input")
    
    location_name = st.text_input("Nome do local (opcional)", placeholder="Ex: Restaurante XYZ", key="loc_name")
    
    return lat, lon, location_name

def show_analysis_page():
    """Página principal de análise de fotos."""
    st.markdown("## 📸 Análise de Refeição")
    
    # Tabs para foto ou texto
    tab1, tab2 = st.tabs(["📷 Tirar Foto", "✍️ Descrever Refeição"])
    
    with tab1:
        st.markdown("Tire uma foto do seu prato para análise automática:")
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
        description_input = st.text_area(
            "Descreva sua refeição",
            placeholder="Ex: 1 prato de arroz, 100g de frango grelhado, salada de alface com tomate",
            height=100,
            key="desc_input"
        )
    
    st.divider()
    
    # Informações adicionais
    col1, col2 = st.columns(2)
    with col1:
        meal_type = st.selectbox(
            "Tipo de refeição",
            ["breakfast", "lunch", "dinner", "snack"],
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
    lat, lon, location_name = get_location_component()
    
    st.divider()
    
    # Botão de análise
    if st.button("🔍 Analisar Refeição", use_container_width=True, type="primary"):
        nutrients = None
        
        # Análise por foto
        if 'image_bytes' in dir() and image_bytes:
            with st.spinner("🤖 Analisando imagem com IA..."):
                nutrients = analyze_meal_photo(image_bytes)
        # Análise por texto
        elif description_input:
            with st.spinner("🔍 Buscando informações nutricionais..."):
                nutrients = analyze_meal_by_description(description_input)
        else:
            st.warning("Por favor, tire uma foto ou descreva sua refeição.")
            return
        
        # Verifica se houve erro
        if nutrients and 'error' in nutrients:
            st.error(f"❌ {nutrients['error']}")
            st.info("💡 Dica: Tente descrever os alimentos em inglês com quantidades (ex: '100g chicken breast, 1 cup cooked rice, 50g broccoli')")
            return
        
        if nutrients:
            show_analysis_results(nutrients, meal_type, meal_date, lat, lon, location_name)
        else:
            st.error("❌ Não foi possível analisar a refeição. Tente novamente ou descreva manualmente.")

def show_analysis_results(nutrients, meal_type, meal_date, lat, lon, location_name):
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
        latitude=lat if lat != 0 else None,
        longitude=lon if lon != 0 else None,
        location_name=location_name if location_name else None
    )
    
    meal_id = save_meal(meal)
    st.success(f"💾 Refeição salva com sucesso! (ID: {meal_id})")

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

def show_map():
    """Exibe mapa com localizações das refeições."""
    st.markdown("## 🗺️ Mapa de Refeições")
    
    meals = get_meals_with_location(st.session_state.user_id)
    
    if not meals:
        st.info("Nenhuma refeição com localização registrada. Adicione latitude e longitude ao registrar suas refeições!")
        return
    
    # Preparar dados para o mapa
    map_data = pd.DataFrame([{
        'lat': m['latitude'],
        'lon': m['longitude'],
        'location': m['location_name'] or 'Local não nomeado',
        'date': m['date'].strftime('%d/%m/%Y') if hasattr(m['date'], 'strftime') else str(m['date']),
        'calories': m['calories'],
        'description': m['description'][:50] if m['description'] else 'Sem descrição'
    } for m in meals if m['latitude'] and m['longitude']])
    
    if map_data.empty:
        st.info("Nenhuma refeição com coordenadas válidas.")
        return
    
    st.map(map_data, latitude='lat', longitude='lon', size=100, color='#2E7D32')
    
    # Lista de locais
    st.divider()
    st.markdown("### 📍 Detalhes dos Locais")
    
    for meal in meals:
        if meal['latitude'] and meal['longitude']:
            with st.expander(f"📍 {meal['location_name'] or 'Local'} - {meal['date']}"):
                st.write(f"**Descrição:** {meal['description'] or 'N/A'}")
                st.write(f"**Calorias:** {meal['calories']:.1f} kcal")
                st.write(f"**Coordenadas:** {meal['latitude']:.6f}, {meal['longitude']:.6f}")
                
                # Link para Google Maps
                maps_url = f"https://www.google.com/maps?q={meal['latitude']},{meal['longitude']}"
                st.markdown(f"[🗺️ Abrir no Google Maps]({maps_url})")

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
            if st.button("🗄️ Criar Backup MySQL (mysqldump)", use_container_width=True):
                with st.spinner("Executando mysqldump..."):
                    try:
                        filepath = mysql_dump()
                        if filepath:
                            st.success(f"✅ Dump MySQL criado!")
                            st.code(filepath)
                        else:
                            st.warning("⚠️ mysqldump não disponível ou não é MySQL.")
                    except Exception as e:
                        st.error(f"❌ Erro: {str(e)}")
    
    with tab2:
        st.markdown("### Restaurar de backup")
        st.warning("⚠️ A restauração pode sobrescrever dados existentes. Faça backup antes!")
        
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

# Main app
def main():
    init_session_state()
    
    if not st.session_state.logged_in:
        show_login_page()
    else:
        page = show_sidebar()
        
        if page == "📸 Nova Análise":
            show_analysis_page()
        elif page == "📊 Resumo Diário":
            show_daily_summary()
        elif page == "📈 Histórico":
            show_history()
        elif page == "🗺️ Mapa de Refeições":
            show_map()
        elif page == "📄 Relatórios":
            show_reports_page()
        elif page == "💾 Backup/Restore":
            show_backup_page()

if __name__ == "__main__":
    main()
