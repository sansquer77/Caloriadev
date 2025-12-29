"""📊 Caloria Dev - Rastreador Nutricional Inteligente

NOVAS FUNCIONALIDADES (v2.6):
- 🍴 Parser inteligente: quebra refeições em itens separados
- 💺 Itens individuais salvos no banco (rastreamento granular)
- 📊 Relatórios com fibras e análise nutricional
- 🦪 Análise semanal/mensal com insights do Perplexity
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from db import init_db, SessionLocal, User, Meal, MealItem
from api_perplexity import analyze_meal_by_description
from meal_parser import parse_and_analyze_meal
from nutrition_analysis import get_nutrition_analysis, compare_with_recommendations
from off_cache_manager import add_to_cache, get_from_cache
import json

# Configuração
st.set_page_config(
    page_title="🍴 Caloria Dev",
    page_icon="🍴",
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
    </style>
""", unsafe_allow_html=True)

# Inicializar DB
init_db()

# State session
if 'user_id' not in st.session_state:
    st.session_state.user_id = 1  # Simplificado para demo

if 'last_analysis' not in st.session_state:
    st.session_state.last_analysis = None


# ===================== HEADER =====================
st.markdown("<div class='header'>🍴 CALORIA DEV - Rastreador Nutricional</div>", unsafe_allow_html=True)
st.markdown("Analise refeições com precisão, visualize padrões, otimize sua nutrição.")
st.divider()

# ===================== SIDEBAR =====================
with st.sidebar:
    st.markdown("### 📊 Menu")
    page = st.radio(
        "Escolha uma opção:",
        ["Registrar Refeição", "Histórico", "Relatórios", "Configurações"]
    )


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
                            # Criar refeição
                            meal = Meal(
                                user_id=st.session_state.user_id,
                                date=meal_date.strftime('%Y-%m-%d'),
                                meal_type=meal_type.lower().replace(" da manhã", "_breakfast"),
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
                            st.error(f"⚠️ Erro ao salvar: {e}")
                        finally:
                            db.close()
                else:
                    st.error(f"⚠️ Erro na análise: {analysis_result.get('error')}")


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
            ["Café da manhã", "Almoço", "Lanche", "Jantar"],
            default=["Café da manhã", "Almoço", "Lanche", "Jantar"]
        )
    
    # Buscar dados
    db = SessionLocal()
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
            analysis = get_nutrition_analysis(period_data, period_type.lower())
            st.markdown(analysis)
        
        # Comparação com recomendações
        st.markdown("### 🎨 Comparação com Recomendações")
        
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
        
    else:
        st.info("📄 Nenhuma refeição registrada no período selecionado")
    
    db.close()


# ===================== PÁGINA: CONFIGURAÇÕES =====================
elif page == "Configurações":
    st.markdown("<div class='subheader'>⚠️ Configurações do App</div>", unsafe_allow_html=True)
    
    st.info("📄 Seção de configurações em desenvolvimento")
    
    # Versão
    st.markdown("### 🍴 Versão")
    st.write("🔥 **v2.6** - Parser inteligente + Itens individuais + Análise nutricional")


# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #999; font-size: 0.85em;'>
👋 Desenvolvido com ❤️ | Rastreador Nutricional Inteligente
</div>
""", unsafe_allow_html=True)
