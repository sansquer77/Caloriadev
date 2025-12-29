"""
Módulo para gerenciar a tabela TACO (Tabela Brasileira de Composição de Alimentos).
Baixa a tabela oficial e armazena em SQLite para buscas rápidas.
"""

import os
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import re
from difflib import SequenceMatcher

# Caminho do banco de dados TACO
TACO_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'taco.db')
TACO_XLSX_URL = "https://www.tbca.net.br/base_dados/taco4_completo.xlsx"
TACO_XLSX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'taco4_completo.xlsx')

# Cache em memória para buscas frequentes
_taco_cache: Dict[str, Dict] = {}


def download_taco_table() -> bool:
    """
    Baixa a tabela TACO do site oficial.
    Retorna True se o download foi bem-sucedido.
    """
    try:
        import requests
        
        print(f"Baixando tabela TACO de {TACO_XLSX_URL}...")
        response = requests.get(TACO_XLSX_URL, timeout=60)
        
        if response.status_code == 200:
            with open(TACO_XLSX_PATH, 'wb') as f:
                f.write(response.content)
            print(f"Tabela TACO salva em {TACO_XLSX_PATH}")
            return True
        else:
            print(f"Erro ao baixar tabela TACO: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"Erro ao baixar tabela TACO: {e}")
        return False


def convert_xlsx_to_sqlite() -> bool:
    """
    Converte o arquivo Excel da TACO para SQLite.
    Retorna True se a conversão foi bem-sucedida.
    """
    try:
        if not os.path.exists(TACO_XLSX_PATH):
            print("Arquivo TACO não encontrado. Baixando...")
            if not download_taco_table():
                return False
        
        print("Convertendo TACO para SQLite...")
        
        # Ler Excel - a tabela geralmente está na primeira aba
        df = pd.read_excel(TACO_XLSX_PATH, sheet_name=0)
        
        # Normalizar nomes das colunas
        df.columns = df.columns.str.strip().str.lower()
        
        # Mapear colunas para nomes padronizados
        column_mapping = {
            'descrição do alimento': 'nome',
            'descrição': 'nome',
            'alimento': 'nome',
            'energia (kcal)': 'calorias',
            'energia(kcal)': 'calorias',
            'kcal': 'calorias',
            'proteína (g)': 'proteina',
            'proteína(g)': 'proteina',
            'proteínas (g)': 'proteina',
            'lipídeos (g)': 'gordura_total',
            'lipídios (g)': 'gordura_total',
            'lipídeos(g)': 'gordura_total',
            'gorduras totais (g)': 'gordura_total',
            'carboidrato (g)': 'carboidratos',
            'carboidratos (g)': 'carboidratos',
            'carboidrato(g)': 'carboidratos',
            'fibra alimentar (g)': 'fibra',
            'fibra(g)': 'fibra',
            'colesterol (mg)': 'colesterol',
            'sódio (mg)': 'sodio',
            'sodium (mg)': 'sodio',
            'açúcares totais (g)': 'acucar',
            'açúcar (g)': 'acucar',
            'ácidos graxos saturados (g)': 'gordura_saturada',
            'saturados (g)': 'gordura_saturada',
            'potássio (mg)': 'potassio',
        }
        
        # Aplicar mapeamento
        df = df.rename(columns=column_mapping)
        
        # Selecionar apenas colunas relevantes que existem
        required_cols = ['nome']
        optional_cols = ['calorias', 'proteina', 'gordura_total', 'gordura_saturada', 
                        'carboidratos', 'acucar', 'fibra', 'sodio', 'potassio', 'colesterol']
        
        existing_cols = [col for col in required_cols + optional_cols if col in df.columns]
        
        if 'nome' not in existing_cols:
            # Tentar encontrar a coluna de nome
            for col in df.columns:
                if 'alimento' in col.lower() or 'descrição' in col.lower() or 'nome' in col.lower():
                    df = df.rename(columns={col: 'nome'})
                    existing_cols = ['nome'] + [c for c in existing_cols if c != 'nome']
                    break
        
        if 'nome' not in df.columns:
            print(f"Colunas disponíveis: {list(df.columns)}")
            print("Não foi possível encontrar a coluna de nome dos alimentos")
            return False
        
        df = df[existing_cols]
        
        # Remover linhas sem nome
        df = df.dropna(subset=['nome'])
        
        # Converter valores para numérico
        for col in existing_cols:
            if col != 'nome':
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Criar coluna de busca normalizada
        df['nome_normalizado'] = df['nome'].apply(normalize_food_name)
        
        # Adicionar coluna de última atualização
        df['updated_at'] = datetime.now().isoformat()
        
        # Salvar no SQLite
        conn = sqlite3.connect(TACO_DB_PATH)
        df.to_sql('alimentos', conn, if_exists='replace', index=False)
        
        # Criar índice para busca rápida
        conn.execute('CREATE INDEX IF NOT EXISTS idx_nome ON alimentos(nome_normalizado)')
        conn.commit()
        conn.close()
        
        print(f"Tabela TACO convertida: {len(df)} alimentos salvos em {TACO_DB_PATH}")
        return True
        
    except Exception as e:
        print(f"Erro ao converter TACO: {e}")
        import traceback
        traceback.print_exc()
        return False


def normalize_food_name(name: str) -> str:
    """Normaliza nome do alimento para busca."""
    if not name:
        return ""
    
    # Converter para minúsculas
    name = name.lower().strip()
    
    # Remover acentos
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', 'ñ': 'n'
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    
    # Remover caracteres especiais
    name = re.sub(r'[^\w\s]', '', name)
    
    # Remover espaços extras
    name = ' '.join(name.split())
    
    return name


def similarity_score(a: str, b: str) -> float:
    """Calcula similaridade entre duas strings."""
    return SequenceMatcher(None, a, b).ratio()


def search_taco(food_name: str, threshold: float = 0.6) -> Optional[Dict]:
    """
    Busca um alimento na tabela TACO.
    
    Args:
        food_name: Nome do alimento a buscar
        threshold: Limiar mínimo de similaridade (0-1)
    
    Returns:
        Dicionário com dados nutricionais ou None se não encontrado
    """
    global _taco_cache
    
    # Verificar cache
    normalized = normalize_food_name(food_name)
    if normalized in _taco_cache:
        return _taco_cache[normalized]
    
    # Verificar se o banco existe
    if not os.path.exists(TACO_DB_PATH):
        print("Banco TACO não encontrado. Inicializando...")
        if not init_taco_db():
            return None
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 1. Busca exata
        cursor.execute(
            "SELECT * FROM alimentos WHERE nome_normalizado = ? LIMIT 1",
            (normalized,)
        )
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            result['match_type'] = 'exact'
            result['source'] = 'TACO'
            _taco_cache[normalized] = result
            conn.close()
            return result
        
        # 2. Busca parcial (LIKE)
        cursor.execute(
            "SELECT * FROM alimentos WHERE nome_normalizado LIKE ? LIMIT 10",
            (f"%{normalized}%",)
        )
        rows = cursor.fetchall()
        
        if rows:
            # Encontrar melhor match por similaridade
            best_match = None
            best_score = 0
            
            for row in rows:
                score = similarity_score(normalized, row['nome_normalizado'])
                if score > best_score:
                    best_score = score
                    best_match = row
            
            if best_match and best_score >= threshold:
                result = dict(best_match)
                result['match_type'] = 'partial'
                result['match_score'] = best_score
                result['source'] = 'TACO'
                _taco_cache[normalized] = result
                conn.close()
                return result
        
        # 3. Busca por palavras-chave
        words = normalized.split()
        if len(words) > 1:
            for word in words:
                if len(word) > 3:  # Ignorar palavras muito curtas
                    cursor.execute(
                        "SELECT * FROM alimentos WHERE nome_normalizado LIKE ? LIMIT 5",
                        (f"%{word}%",)
                    )
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        score = similarity_score(normalized, row['nome_normalizado'])
                        if score >= threshold:
                            result = dict(row)
                            result['match_type'] = 'keyword'
                            result['match_score'] = score
                            result['source'] = 'TACO'
                            _taco_cache[normalized] = result
                            conn.close()
                            return result
        
        conn.close()
        return None
        
    except Exception as e:
        print(f"Erro ao buscar na TACO: {e}")
        return None


def get_taco_nutrition(food_name: str, quantity_grams: float = 100.0) -> Optional[Dict]:
    """
    Obtém dados nutricionais da TACO ajustados para a quantidade.
    
    Args:
        food_name: Nome do alimento
        quantity_grams: Quantidade em gramas (padrão 100g - base da TACO)
    
    Returns:
        Dicionário com dados nutricionais ajustados ou None
    """
    result = search_taco(food_name)
    
    if not result:
        return None
    
    # Fator de ajuste para quantidade
    factor = quantity_grams / 100.0
    
    return {
        'name': result.get('nome', food_name),
        'quantity': f"{quantity_grams}g",
        'calories': float(result.get('calorias', 0)) * factor,
        'protein': float(result.get('proteina', 0)) * factor,
        'fat_total': float(result.get('gordura_total', 0)) * factor,
        'fat_saturated': float(result.get('gordura_saturada', 0)) * factor,
        'carbs': float(result.get('carboidratos', 0)) * factor,
        'sugar': float(result.get('acucar', 0)) * factor,
        'fiber': float(result.get('fibra', 0)) * factor,
        'sodium': float(result.get('sodio', 0)) * factor,
        'potassium': float(result.get('potassio', 0)) * factor,
        'cholesterol': float(result.get('colesterol', 0)) * factor,
        'source': 'TACO',
        'match_type': result.get('match_type', 'unknown'),
        'original_name': result.get('nome', '')
    }


def init_taco_db() -> bool:
    """
    Inicializa o banco de dados TACO.
    Baixa e converte a tabela se necessário.
    """
    if os.path.exists(TACO_DB_PATH):
        # Verificar se está atualizado (menos de 30 dias)
        try:
            conn = sqlite3.connect(TACO_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT updated_at FROM alimentos LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            
            if row:
                updated_at = datetime.fromisoformat(row[0])
                if datetime.now() - updated_at < timedelta(days=30):
                    print("Banco TACO está atualizado.")
                    return True
        except:
            pass
    
    # Baixar e converter
    return convert_xlsx_to_sqlite()


def get_taco_stats() -> Dict:
    """Retorna estatísticas do banco TACO."""
    if not os.path.exists(TACO_DB_PATH):
        return {'status': 'not_initialized', 'count': 0}
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM alimentos")
        count = cursor.fetchone()[0]
        
        cursor.execute("SELECT updated_at FROM alimentos LIMIT 1")
        updated = cursor.fetchone()
        updated_at = updated[0] if updated else None
        
        conn.close()
        
        return {
            'status': 'ready',
            'count': count,
            'updated_at': updated_at,
            'db_path': TACO_DB_PATH
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def list_taco_foods(limit: int = 100) -> List[str]:
    """Lista alimentos disponíveis na TACO."""
    if not os.path.exists(TACO_DB_PATH):
        return []
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        cursor = conn.cursor()
        cursor.execute(f"SELECT nome FROM alimentos LIMIT {limit}")
        foods = [row[0] for row in cursor.fetchall()]
        conn.close()
        return foods
    except:
        return []
