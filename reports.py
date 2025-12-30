"""
Módulo de Relatórios - Consolidação de dados e exportação PDF.
Inclui análise nutricional via Perplexity AI.
"""

import os
import io
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from storage import get_aggregated_macros, get_user_meals, get_user_by_id
from db import get_session, Meal, User
from sqlalchemy import func
import requests


# Configuração Perplexity
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
PERPLEXITY_API_URL = 'https://api.perplexity.ai/chat/completions'


def get_period_dates(period: str, reference_date: Optional[date] = None) -> Tuple[date, date]:
    """
    Retorna as datas de início e fim para um período.
    
    Args:
        period: 'day', 'week', 'month', 'year'
        reference_date: Data de referência (padrão: hoje)
    
    Returns:
        Tupla (start_date, end_date)
    """
    if reference_date is None:
        reference_date = date.today()
    
    if period == 'day':
        return reference_date, reference_date
    
    elif period == 'week':
        # Início da semana (segunda-feira)
        start = reference_date - timedelta(days=reference_date.weekday())
        end = start + timedelta(days=6)
        return start, end
    
    elif period == 'month':
        start = reference_date.replace(day=1)
        # Último dia do mês
        if reference_date.month == 12:
            end = reference_date.replace(day=31)
        else:
            end = reference_date.replace(month=reference_date.month + 1, day=1) - timedelta(days=1)
        return start, end
    
    elif period == 'year':
        start = reference_date.replace(month=1, day=1)
        end = reference_date.replace(month=12, day=31)
        return start, end
    
    else:
        return reference_date, reference_date


def get_daily_breakdown(user_id: int, start_date: date, end_date: date) -> List[Dict]:
    """
    Retorna breakdown diário de nutrientes no período.
    """
    session = get_session()
    try:
        results = session.query(
            Meal.date,
            func.sum(Meal.calories).label('calories'),
            func.sum(Meal.protein).label('protein'),
            func.sum(Meal.carbs).label('carbs'),
            func.sum(Meal.fat_total).label('fat_total'),
            func.sum(Meal.sugar).label('sugar'),
            func.sum(Meal.fiber).label('fiber'),
            func.sum(Meal.sodium).label('sodium'),
            func.count(Meal.id).label('meal_count')
        ).filter(
            Meal.user_id == user_id,
            Meal.date >= start_date,
            Meal.date <= end_date
        ).group_by(Meal.date).order_by(Meal.date).all()
        rows = []
        for r in results:
            # Meal.date may be stored as string; coerce to date when possible
            d = r.date
            if isinstance(d, str):
                try:
                    d = datetime.fromisoformat(d).date()
                except Exception:
                    try:
                        d = datetime.strptime(d, '%Y-%m-%d').date()
                    except Exception:
                        pass

            rows.append({
                'date': d,
                'calories': float(r.calories or 0),
                'protein': float(r.protein or 0),
                'carbs': float(r.carbs or 0),
                'fat_total': float(r.fat_total or 0),
                'sugar': float(r.sugar or 0),
                'fiber': float(r.fiber or 0),
                'sodium': float(getattr(r, 'sodium', 0) or 0),
                'meal_count': int(r.meal_count or 0)
            })
        return rows
    finally:
        session.close()


def get_meal_type_breakdown(user_id: int, start_date: date, end_date: date) -> Dict:
    """
    Retorna breakdown por tipo de refeição.
    """
    session = get_session()
    try:
        results = session.query(
            Meal.meal_type,
            func.sum(Meal.calories).label('calories'),
            func.sum(Meal.protein).label('protein'),
            func.sum(Meal.carbs).label('carbs'),
            func.sum(Meal.fat_total).label('fat_total'),
            func.count(Meal.id).label('count')
        ).filter(
            Meal.user_id == user_id,
            Meal.date >= start_date,
            Meal.date <= end_date
        ).group_by(Meal.meal_type).all()
        
        meal_types = {
            'breakfast': {'name': 'Café da manhã', 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'count': 0},
            'lunch': {'name': 'Almoço', 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'count': 0},
            'dinner': {'name': 'Jantar', 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'count': 0},
            'snack': {'name': 'Lanche', 'calories': 0, 'protein': 0, 'carbs': 0, 'fat': 0, 'count': 0}
        }
        
        for r in results:
            if r.meal_type in meal_types:
                meal_types[r.meal_type].update({
                    'calories': r.calories or 0,
                    'protein': r.protein or 0,
                    'carbs': r.carbs or 0,
                    'fat': r.fat_total or 0,
                    'count': r.count or 0
                })
        
        return meal_types
    finally:
        session.close()


def generate_ai_analysis(data: Dict, user_info: Dict, period: str) -> str:
    """
    Gera análise nutricional usando Perplexity AI.
    """
    if not PERPLEXITY_API_KEY:
        return "Análise de IA não disponível (API key não configurada)."
    
    # Preparar prompt com os dados
    period_names = {
        'day': 'diário',
        'week': 'semanal',
        'month': 'mensal',
        'year': 'anual'
    }
    
    prompt = f"""Você é um nutricionista especialista. Analise os seguintes dados nutricionais e forneça uma análise profissional em português brasileiro.

DADOS DO PERÍODO ({period_names.get(period, period)}):
- Calorias totais: {data.get('calories', 0):.0f} kcal
- Proteínas: {data.get('protein', 0):.1f}g
- Carboidratos: {data.get('carbs', 0):.1f}g
- Gorduras totais: {data.get('fat_total', 0):.1f}g
- Açúcares: {data.get('sugar', 0):.1f}g
- Fibras: {data.get('fiber', 0):.1f}g
- Número de dias: {data.get('days', 1)}
- Total de refeições: {data.get('meal_count', 0)}

DADOS DO USUÁRIO:
- Peso: {user_info.get('weight', 'não informado')} kg
- Altura: {user_info.get('height', 'não informado')} m
- Limite calórico diário: {user_info.get('cal_limit', 'não definido')} kcal

Por favor, forneça:
1. Uma avaliação geral do consumo
2. Pontos positivos identificados
3. Pontos de atenção/melhoria
4. Recomendações específicas
5. Comparação com valores diários recomendados (VDR)

Seja objetivo e profissional, mas acessível. Limite a resposta a 400 palavras."""

    headers = {
        'Authorization': f'Bearer {PERPLEXITY_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "Você é um nutricionista profissional especializado em análise de dados nutricionais."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 1000,
        "temperature": 0.3
    }
    
    try:
        response = requests.post(PERPLEXITY_API_URL, json=payload, headers=headers, timeout=60)
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
        return f"Não foi possível gerar análise. Status: {response.status_code}"
    except Exception as e:
        return f"Erro ao gerar análise: {str(e)}"


def create_macro_pie_chart(data: Dict) -> Drawing:
    """
    Cria gráfico de pizza dos macronutrientes.
    """
    drawing = Drawing(200, 150)
    
    # Calcular proporções
    protein = data.get('protein', 0)
    carbs = data.get('carbs', 0)
    fat = data.get('fat_total', 0)
    total = protein + carbs + fat
    
    if total == 0:
        return drawing
    
    pie = Pie()
    pie.x = 50
    pie.y = 25
    pie.width = 100
    pie.height = 100
    pie.data = [protein, carbs, fat]
    pie.labels = [f'Proteína\n{protein:.0f}g', f'Carboidrato\n{carbs:.0f}g', f'Gordura\n{fat:.0f}g']
    pie.slices[0].fillColor = colors.HexColor('#4CAF50')  # Verde
    pie.slices[1].fillColor = colors.HexColor('#2196F3')  # Azul
    pie.slices[2].fillColor = colors.HexColor('#FF9800')  # Laranja
    pie.slices.strokeWidth = 0.5
    
    drawing.add(pie)
    return drawing


def generate_pdf_report(
    user_id: int,
    period: str,
    reference_date: Optional[date] = None,
    include_ai_analysis: bool = True
) -> bytes:
    """
    Gera relatório PDF completo.
    
    Args:
        user_id: ID do usuário
        period: 'day', 'week', 'month', 'year'
        reference_date: Data de referência
        include_ai_analysis: Se deve incluir análise da IA
    
    Returns:
        Bytes do PDF gerado
    """
    # Obter datas do período
    start_date, end_date = get_period_dates(period, reference_date)
    
    # Obter dados do usuário
    user_info = get_user_by_id(user_id) or {}
    
    # Obter dados consolidados
    macros = get_aggregated_macros(user_id, start_date, end_date)
    daily_data = get_daily_breakdown(user_id, start_date, end_date)
    meal_types = get_meal_type_breakdown(user_id, start_date, end_date)
    
    # Calcular estatísticas
    days_count = (end_date - start_date).days + 1
    days_with_data = len(daily_data)
    total_meals = sum(d['meal_count'] for d in daily_data)
    
    # Médias diárias
    if days_with_data > 0:
        avg_calories = macros['calories'] / days_with_data
        avg_protein = macros['protein'] / days_with_data
        avg_carbs = macros['carbs'] / days_with_data
        avg_fat = macros['fat_total'] / days_with_data
    else:
        avg_calories = avg_protein = avg_carbs = avg_fat = 0
    
    # Preparar buffer para PDF
    buffer = io.BytesIO()
    
    # Criar documento
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Title2',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#2E7D32'),
        spaceAfter=30
    ))
    styles.add(ParagraphStyle(
        name='Subtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#666666'),
        spaceAfter=20
    ))
    styles.add(ParagraphStyle(
        name='SectionTitle',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2E7D32'),
        spaceBefore=20,
        spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name='BodyText2',
        parent=styles['BodyText'],
        fontSize=11,
        alignment=TA_JUSTIFY,
        spaceAfter=10
    ))
    
    # Conteúdo
    content = []
    
    # Título
    period_names = {
        'day': 'Diário',
        'week': 'Semanal',
        'month': 'Mensal',
        'year': 'Anual'
    }
    
    content.append(Paragraph("🍽️ Caloria", styles['Title2']))
    content.append(Paragraph(
        f"Relatório Nutricional {period_names.get(period, period)}",
        styles['Subtitle']
    ))
    content.append(Paragraph(
        f"Período: {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}",
        styles['Normal']
    ))
    content.append(Paragraph(
        f"Usuário: {user_info.get('username', 'N/A')}",
        styles['Normal']
    ))
    content.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        styles['Normal']
    ))
    
    content.append(Spacer(1, 20))
    content.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2E7D32')))
    content.append(Spacer(1, 20))
    
    # Resumo Geral
    content.append(Paragraph("📊 Resumo Geral", styles['SectionTitle']))
    
    summary_data = [
        ['Métrica', 'Total', 'Média Diária'],
        ['Calorias', f"{macros['calories']:.0f} kcal", f"{avg_calories:.0f} kcal"],
        ['Proteínas', f"{macros['protein']:.1f} g", f"{avg_protein:.1f} g"],
        ['Carboidratos', f"{macros['carbs']:.1f} g", f"{avg_carbs:.1f} g"],
        ['Gorduras', f"{macros['fat_total']:.1f} g", f"{avg_fat:.1f} g"],
        ['Açúcares', f"{macros['sugar']:.1f} g", f"{macros['sugar']/max(days_with_data,1):.1f} g"],
        ['Fibras', f"{macros['fiber']:.1f} g", f"{macros['fiber']/max(days_with_data,1):.1f} g"],
        ['Sódio', f"{macros.get('sodium', 0):.0f} mg", f"{macros.get('sodium', 0)/max(days_with_data,1):.0f} mg"],
    ]
    
    summary_table = Table(summary_data, colWidths=[6*cm, 5*cm, 5*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    content.append(summary_table)
    
    content.append(Spacer(1, 10))
    content.append(Paragraph(
        f"<b>Dias no período:</b> {days_count} | <b>Dias com registros:</b> {days_with_data} | <b>Total de refeições:</b> {total_meals}",
        styles['Normal']
    ))
    
    content.append(Spacer(1, 20))
    
    # Distribuição por Refeição
    content.append(Paragraph("🍴 Distribuição por Tipo de Refeição", styles['SectionTitle']))
    
    meal_data = [['Refeição', 'Qtd', 'Calorias', 'Proteína', 'Carboidrato', 'Gordura']]
    for meal_type, info in meal_types.items():
        meal_data.append([
            info['name'],
            str(info['count']),
            f"{info['calories']:.0f}",
            f"{info['protein']:.1f}g",
            f"{info['carbs']:.1f}g",
            f"{info['fat']:.1f}g"
        ])
    
    meal_table = Table(meal_data, colWidths=[4*cm, 2*cm, 3*cm, 3*cm, 3*cm, 3*cm])
    meal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ]))
    content.append(meal_table)
    
    # Detalhamento Diário (se houver dados e não for muito longo)
    if daily_data and len(daily_data) <= 31:
        content.append(Spacer(1, 20))
        content.append(Paragraph("📅 Detalhamento Diário", styles['SectionTitle']))
        
        daily_table_data = [['Data', 'Refeições', 'Calorias', 'Proteína', 'Carbs', 'Gordura']]
        for day in daily_data:
            daily_table_data.append([
                day['date'].strftime('%d/%m'),
                str(day['meal_count']),
                f"{day['calories']:.0f}",
                f"{day['protein']:.1f}g",
                f"{day['carbs']:.1f}g",
                f"{day['fat_total']:.1f}g"
            ])
        
        daily_table = Table(daily_table_data, colWidths=[3*cm, 2.5*cm, 3*cm, 3*cm, 3*cm, 3*cm])
        daily_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2196F3')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f7ff')]),
        ]))
        content.append(daily_table)
    
    # Metas do Usuário
    if user_info.get('cal_limit'):
        content.append(Spacer(1, 20))
        content.append(Paragraph("🎯 Comparação com Metas", styles['SectionTitle']))
        
        goals_data = [['Nutriente', 'Meta Diária', 'Média Consumida', 'Status']]
        
        # Calcular status
        def get_status(avg, limit):
            if limit is None or limit == 0:
                return 'N/A'
            pct = (avg / limit) * 100
            if pct < 90:
                return f'✅ {pct:.0f}%'
            elif pct <= 110:
                return f'👍 {pct:.0f}%'
            else:
                return f'⚠️ {pct:.0f}%'
        
        if user_info.get('cal_limit'):
            goals_data.append(['Calorias', f"{user_info['cal_limit']:.0f} kcal", 
                             f"{avg_calories:.0f} kcal", get_status(avg_calories, user_info['cal_limit'])])
        if user_info.get('protein_limit'):
            goals_data.append(['Proteínas', f"{user_info['protein_limit']:.0f} g",
                             f"{avg_protein:.1f} g", get_status(avg_protein, user_info['protein_limit'])])
        if user_info.get('carbs_limit'):
            goals_data.append(['Carboidratos', f"{user_info['carbs_limit']:.0f} g",
                             f"{avg_carbs:.1f} g", get_status(avg_carbs, user_info['carbs_limit'])])
        if user_info.get('fat_limit'):
            goals_data.append(['Gorduras', f"{user_info['fat_limit']:.0f} g",
                             f"{avg_fat:.1f} g", get_status(avg_fat, user_info['fat_limit'])])
        
        if len(goals_data) > 1:
            goals_table = Table(goals_data, colWidths=[4*cm, 4*cm, 4*cm, 4*cm])
            goals_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FF9800')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            content.append(goals_table)
    
    # Rodapé
    content.append(Spacer(1, 30))
    content.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    content.append(Spacer(1, 10))
    content.append(Paragraph(
        "<i>Relatório gerado automaticamente pelo Caloria App. "
        "As informações nutricionais são estimativas baseadas nos dados registrados. "
        "Consulte um profissional de saúde para orientação personalizada.</i>",
        ParagraphStyle(name='Footer', fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    ))
    
    # Gerar PDF
    doc.build(content)
    
    # Retornar bytes
    buffer.seek(0)
    return buffer.getvalue()


def get_report_filename(period: str, start_date: date, end_date: date) -> str:
    """Gera nome do arquivo para o relatório."""
    if period == 'day':
        return f"relatorio_{start_date.strftime('%Y%m%d')}.pdf"
    else:
        return f"relatorio_{period}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
