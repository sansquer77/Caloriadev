import streamlit as st
from datetime import date
from auth import generate_token, decode_token, create_password_hash, verify_password_hash
from api_perplexity import analyze_meal_photo
from models import MealData
from storage import save_meal, get_daily_macros, get_aggregated_macros, create_user

st.title("Análise de Refeições por Foto")

# Tela de cadastro rápido (simplificado)
if 'token' not in st.session_state:
    with st.form("Cadastro"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type='password')
        weight = st.number_input("Peso (kg)", min_value=0.0, format="%.1f")
        height = st.number_input("Altura (m)", min_value=0.0, format="%.2f")
        cal_limit = st.number_input("Limite Calorias", min_value=0.0)
        protein_limit = st.number_input("Limite Proteínas (g)", min_value=0.0)
        fat_limit = st.number_input("Limite Gorduras (g)", min_value=0.0)
        carbs_limit = st.number_input("Limite Carboidratos (g)", min_value=0.0)
        sugar_limit = st.number_input("Limite Açúcares (g)", min_value=0.0)

        submit = st.form_submit_button("Cadastrar")
        if submit:
            pwd_hash = create_password_hash(password)
            create_user(username, pwd_hash, weight, height, cal_limit, protein_limit, fat_limit,
                        carbs_limit, sugar_limit)
            st.success("Usuário cadastrado! Faça login.")

else:
    st.write("Autenticado")
    # Upload/câmera foto
    img_file_buffer = st.camera_input("Tire a foto do prato")
    if img_file_buffer is not None:
        img_bytes = img_file_buffer.getvalue()
        # Análise IA
        with st.spinner("Analisando a foto..."):
            nutrients = analyze_meal_photo(img_bytes)
            if nutrients:
                # Salvar resultado
                today = date.today()
                meal = MealData(
                    user_id=1,  # Simples para demo, substituir com id do usuário logado
                    date=today,
                    meal_type="lunch",
                    calories=nutrients['calories'],
                    protein=nutrients['protein'],
                    fat=nutrients['fat'],
                    carbs=nutrients['carbs'],
                    sugar=nutrients['sugar']
                )
                save_meal(meal)
                st.success(f"Analisado! Calorias: {nutrients['calories']:.1f}")
            else:
                st.error("Erro na análise da foto.")

    # Mostrar totais por semana/mês
    # Implementar exceções e controle de usuário real
