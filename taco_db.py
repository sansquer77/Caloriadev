"""
Módulo para gerenciar a tabela TACO (Tabela Brasileira de Composição de Alimentos).
Baixa a tabela oficial e armazena no banco caloria.db para buscas rápidas.

ATUALIZAÇÃO: Agora usa o banco consolidado caloria.db em vez de taco.db separado.
"""

import os
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import re
from difflib import SequenceMatcher

# ATUALIZADO: Usar o mesmo banco caloria.db
TACO_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'caloria.db')

# URLs alternativas para download da tabela TACO (a maioria dos sites bloqueiam download direto)
# Se todas falharem, criamos uma tabela com alimentos básicos brasileiros
TACO_URLS = [
    "https://nepa.unicamp.br/arquivo/uploads/taco-4a-edicao/taco-4a-edicao-2/Taco4_edicao_ampliada_e_revisada.xlsx",
    "https://www.nepa.unicamp.br/taco/arquivos/taco_4_edicao_ampliada_e_revisada.xlsx",
]
TACO_XLSX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'taco4_completo.xlsx')

# Cache em memória para buscas frequentes
_taco_cache: Dict[str, Dict] = {}


def download_taco_table() -> bool:
    """
    Baixa a tabela TACO de fontes oficiais.
    Tenta múltiplas URLs em caso de falha.
    Retorna True se o download foi bem-sucedido.
    """
    import requests
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for url in TACO_URLS:
        try:
            print(f"Tentando baixar tabela TACO de {url}...")
            response = requests.get(url, headers=headers, timeout=120, allow_redirects=True)
            
            if response.status_code == 200 and len(response.content) > 10000:
                with open(TACO_XLSX_PATH, 'wb') as f:
                    f.write(response.content)
                print(f"Tabela TACO salva em {TACO_XLSX_PATH} ({len(response.content)} bytes)")
                return True
            else:
                print(f"Resposta inválida de {url}: HTTP {response.status_code}, tamanho: {len(response.content)}")
        except Exception as e:
            print(f"Erro ao baixar de {url}: {e}")
            continue
    
    # Se todas falharam, criar tabela básica manualmente
    print("Download falhou. Criando tabela básica com alimentos comuns...")
    return create_basic_taco_table()


def create_basic_taco_table() -> bool:
    """
    Cria uma tabela básica com alimentos brasileiros comuns.
    Usada como fallback quando o download falha.
    Dados baseados na TACO 4ª edição.
    """
    # Dados nutricionais por 100g - baseados na TACO
    alimentos = [
        # Cereais e derivados
        {"nome": "Arroz branco cozido", "calorias": 128, "proteina": 2.5, "gordura_total": 0.2, "carboidratos": 28.1, "fibra": 1.6, "sodio": 1},
        {"nome": "Arroz integral cozido", "calorias": 124, "proteina": 2.6, "gordura_total": 1.0, "carboidratos": 25.8, "fibra": 2.7, "sodio": 1},
        {"nome": "Feijão preto cozido", "calorias": 77, "proteina": 4.5, "gordura_total": 0.5, "carboidratos": 14.0, "fibra": 8.4, "sodio": 2},
        {"nome": "Feijão carioca cozido", "calorias": 76, "proteina": 4.8, "gordura_total": 0.5, "carboidratos": 13.6, "fibra": 8.5, "sodio": 2},
        {"nome": "Macarrão cozido", "calorias": 102, "proteina": 3.4, "gordura_total": 0.5, "carboidratos": 21.8, "fibra": 1.0, "sodio": 1},
        {"nome": "Pão francês", "calorias": 300, "proteina": 8.0, "gordura_total": 3.1, "carboidratos": 58.6, "fibra": 2.3, "sodio": 648},
        {"nome": "Pão de forma", "calorias": 253, "proteina": 7.9, "gordura_total": 2.8, "carboidratos": 49.9, "fibra": 2.5, "sodio": 496},
        {"nome": "Farofa", "calorias": 403, "proteina": 1.7, "gordura_total": 16.5, "carboidratos": 62.4, "fibra": 6.4, "sodio": 574},
        {"nome": "Farinha de mandioca", "calorias": 361, "proteina": 1.2, "gordura_total": 0.3, "carboidratos": 87.9, "fibra": 6.5, "sodio": 2},
        
        # Carnes e ovos
        {"nome": "Frango grelhado", "calorias": 159, "proteina": 32.0, "gordura_total": 2.5, "carboidratos": 0, "fibra": 0, "sodio": 74},
        {"nome": "Peito de frango grelhado", "calorias": 159, "proteina": 32.0, "gordura_total": 2.5, "carboidratos": 0, "fibra": 0, "sodio": 74},
        {"nome": "Carne bovina grelhada", "calorias": 219, "proteina": 32.4, "gordura_total": 9.4, "carboidratos": 0, "fibra": 0, "sodio": 51},
        {"nome": "Carne moída refogada", "calorias": 212, "proteina": 26.7, "gordura_total": 11.6, "carboidratos": 0, "fibra": 0, "sodio": 50},
        {"nome": "Pernil assado", "calorias": 262, "proteina": 27.0, "gordura_total": 16.5, "carboidratos": 0, "fibra": 0, "sodio": 65},
        {"nome": "Costela bovina assada", "calorias": 292, "proteina": 24.7, "gordura_total": 21.3, "carboidratos": 0, "fibra": 0, "sodio": 48},
        {"nome": "Linguiça frita", "calorias": 296, "proteina": 16.1, "gordura_total": 24.6, "carboidratos": 2.7, "fibra": 0, "sodio": 1118},
        {"nome": "Ovo frito", "calorias": 240, "proteina": 15.6, "gordura_total": 19.6, "carboidratos": 0.6, "fibra": 0, "sodio": 364},
        {"nome": "Ovo cozido", "calorias": 146, "proteina": 13.3, "gordura_total": 9.5, "carboidratos": 0.6, "fibra": 0, "sodio": 146},
        {"nome": "Peixe grelhado", "calorias": 111, "proteina": 23.0, "gordura_total": 1.7, "carboidratos": 0, "fibra": 0, "sodio": 88},
        
        # Laticínios
        {"nome": "Leite integral", "calorias": 61, "proteina": 3.2, "gordura_total": 3.3, "carboidratos": 4.5, "fibra": 0, "sodio": 50},
        {"nome": "Queijo mussarela", "calorias": 330, "proteina": 22.6, "gordura_total": 25.2, "carboidratos": 3.0, "fibra": 0, "sodio": 581},
        {"nome": "Queijo minas frescal", "calorias": 264, "proteina": 17.4, "gordura_total": 20.2, "carboidratos": 3.2, "fibra": 0, "sodio": 343},
        {"nome": "Iogurte natural", "calorias": 51, "proteina": 4.1, "gordura_total": 1.5, "carboidratos": 5.4, "fibra": 0, "sodio": 52},
        {"nome": "Manteiga", "calorias": 726, "proteina": 0.4, "gordura_total": 82.4, "carboidratos": 0, "fibra": 0, "sodio": 11},
        
        # Vegetais
        {"nome": "Alface", "calorias": 11, "proteina": 1.3, "gordura_total": 0.2, "carboidratos": 1.7, "fibra": 1.0, "sodio": 3},
        {"nome": "Tomate", "calorias": 15, "proteina": 1.1, "gordura_total": 0.2, "carboidratos": 3.1, "fibra": 1.2, "sodio": 2},
        {"nome": "Cebola", "calorias": 39, "proteina": 1.7, "gordura_total": 0.1, "carboidratos": 8.9, "fibra": 2.2, "sodio": 1},
        {"nome": "Batata cozida", "calorias": 52, "proteina": 1.2, "gordura_total": 0.1, "carboidratos": 11.9, "fibra": 1.3, "sodio": 2},
        {"nome": "Batata frita", "calorias": 267, "proteina": 4.0, "gordura_total": 12.0, "carboidratos": 36.0, "fibra": 3.0, "sodio": 312},
        {"nome": "Cenoura cozida", "calorias": 30, "proteina": 0.8, "gordura_total": 0.2, "carboidratos": 6.7, "fibra": 2.6, "sodio": 42},
        {"nome": "Brócolis cozido", "calorias": 25, "proteina": 2.1, "gordura_total": 0.5, "carboidratos": 4.4, "fibra": 3.4, "sodio": 6},
        {"nome": "Couve refogada", "calorias": 90, "proteina": 2.9, "gordura_total": 6.7, "carboidratos": 5.7, "fibra": 5.7, "sodio": 96},
        {"nome": "Maionese de batata", "calorias": 150, "proteina": 1.5, "gordura_total": 10.0, "carboidratos": 14.0, "fibra": 1.0, "sodio": 400},
        
        # Frutas
        {"nome": "Banana", "calorias": 92, "proteina": 1.4, "gordura_total": 0.1, "carboidratos": 23.8, "fibra": 2.0, "sodio": 1},
        {"nome": "Maçã", "calorias": 56, "proteina": 0.3, "gordura_total": 0.0, "carboidratos": 15.2, "fibra": 1.3, "sodio": 0},
        {"nome": "Laranja", "calorias": 37, "proteina": 1.0, "gordura_total": 0.1, "carboidratos": 8.9, "fibra": 0.8, "sodio": 1},
        {"nome": "Mamão", "calorias": 40, "proteina": 0.5, "gordura_total": 0.1, "carboidratos": 10.4, "fibra": 1.0, "sodio": 3},
        {"nome": "Melancia", "calorias": 33, "proteina": 0.9, "gordura_total": 0.0, "carboidratos": 8.1, "fibra": 0.1, "sodio": 1},
        {"nome": "Abacaxi", "calorias": 48, "proteina": 0.9, "gordura_total": 0.1, "carboidratos": 12.3, "fibra": 1.0, "sodio": 1},
        
        # Bebidas
        {"nome": "Suco de laranja", "calorias": 45, "proteina": 0.7, "gordura_total": 0.2, "carboidratos": 10.4, "fibra": 0.1, "sodio": 1},
        {"nome": "Café com açúcar", "calorias": 61, "proteina": 0.5, "gordura_total": 0.2, "carboidratos": 14.4, "fibra": 0, "sodio": 2},
        {"nome": "Refrigerante cola", "calorias": 42, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 10.6, "fibra": 0, "sodio": 4},
        {"nome": "Cerveja", "calorias": 42, "proteina": 0.3, "gordura_total": 0.0, "carboidratos": 3.5, "fibra": 0, "sodio": 4},
        
        # Doces e sobremesas
        {"nome": "Açúcar", "calorias": 387, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 99.5, "fibra": 0, "sodio": 1},
        {"nome": "Chocolate ao leite", "calorias": 540, "proteina": 7.0, "gordura_total": 30.0, "carboidratos": 60.0, "fibra": 2.0, "sodio": 60},
        {"nome": "Bolo de chocolate", "calorias": 347, "proteina": 5.0, "gordura_total": 14.0, "carboidratos": 53.0, "fibra": 2.0, "sodio": 320},
        {"nome": "Sorvete", "calorias": 201, "proteina": 3.5, "gordura_total": 10.5, "carboidratos": 23.4, "fibra": 0, "sodio": 70},
        {"nome": "Pudim de leite", "calorias": 180, "proteina": 5.0, "gordura_total": 5.5, "carboidratos": 28.0, "fibra": 0, "sodio": 75},
        
        # Pratos típicos
        {"nome": "Feijoada", "calorias": 145, "proteina": 9.5, "gordura_total": 6.5, "carboidratos": 12.0, "fibra": 6.0, "sodio": 450},
        {"nome": "Strogonoff de frango", "calorias": 170, "proteina": 15.0, "gordura_total": 10.0, "carboidratos": 5.0, "fibra": 0.5, "sodio": 350},
        {"nome": "Moqueca de peixe", "calorias": 130, "proteina": 14.0, "gordura_total": 6.5, "carboidratos": 4.0, "fibra": 1.0, "sodio": 320},
        {"nome": "Açaí", "calorias": 58, "proteina": 0.8, "gordura_total": 3.9, "carboidratos": 6.2, "fibra": 2.6, "sodio": 5},
        {"nome": "Tapioca", "calorias": 340, "proteina": 0.1, "gordura_total": 0.1, "carboidratos": 87.0, "fibra": 0.3, "sodio": 1},
        {"nome": "Coxinha", "calorias": 263, "proteina": 9.5, "gordura_total": 13.0, "carboidratos": 27.5, "fibra": 1.0, "sodio": 450},
        {"nome": "Pastel frito", "calorias": 338, "proteina": 7.5, "gordura_total": 19.5, "carboidratos": 34.0, "fibra": 1.0, "sodio": 520},
        {"nome": "Pizza", "calorias": 266, "proteina": 11.0, "gordura_total": 10.0, "carboidratos": 33.0, "fibra": 2.0, "sodio": 620},
        {"nome": "Hambúrguer", "calorias": 295, "proteina": 17.0, "gordura_total": 14.0, "carboidratos": 24.0, "fibra": 1.0, "sodio": 580},
    ]
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        cursor = conn.cursor()
        
        # Criar tabela - agora usando IF NOT EXISTS para não sobrescrever se já existir
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                nome_normalizado TEXT,
                calorias REAL,
                proteina REAL,
                gordura_total REAL,
                gordura_saturada REAL,
                carboidratos REAL,
                acucar REAL,
                fibra REAL,
                sodio REAL,
                potassio REAL,
                colesterol REAL,
                updated_at TEXT
            )
        ''')
        
        # Verificar se já tem dados
        cursor.execute("SELECT COUNT(*) FROM alimentos")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"Tabela TACO já contém {count} alimentos. Pulando inserção.")
            conn.close()
            return True
        
        # Inserir alimentos
        now = datetime.now().isoformat()
        for alimento in alimentos:
            nome_norm = normalize_food_name(alimento['nome'])
            cursor.execute('''
                INSERT INTO alimentos (nome, nome_normalizado, calorias, proteina, gordura_total, 
                    gordura_saturada, carboidratos, acucar, fibra, sodio, potassio, colesterol, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alimento['nome'], nome_norm, alimento['calorias'], alimento['proteina'],
                alimento['gordura_total'], 0, alimento['carboidratos'], 0,
                alimento.get('fibra', 0), alimento.get('sodio', 0), 0, 0, now
            ))
        
        # Criar índice
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_nome_normalizado ON alimentos(nome_normalizado)')
        conn.commit()
        conn.close()
        
        print(f"Tabela básica TACO criada com {len(alimentos)} alimentos comuns")
        return True
        
    except Exception as e:
        print(f"Erro ao criar tabela básica: {e}")
        return False


def convert_xlsx_to_sqlite() -> bool:
    """
    Converte o arquivo Excel da TACO para SQLite.
    Retorna True se a conversão foi bem-sucedida.
    """
    try:
        # Se o banco já existe e tem dados, não precisa converter
        if os.path.exists(TACO_DB_PATH):
            try:
                conn = sqlite3.connect(TACO_DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM alimentos")
                count = cursor.fetchone()[0]
                conn.close()
                if count > 0:
                    print(f"Banco TACO já existe com {count} alimentos.")
                    return True
            except:
                pass
        
        if not os.path.exists(TACO_XLSX_PATH):
            print("Arquivo Excel TACO não encontrado. Tentando baixar...")
            download_result = download_taco_table()
            # Se download_taco_table criou a tabela básica, retorna True
            if download_result and os.path.exists(TACO_DB_PATH):
                return True
            # Se não baixou o Excel e não criou tabela básica, falha
            if not os.path.exists(TACO_XLSX_PATH):
                return False
        
        print("Convertendo TACO Excel para SQLite...")
        
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
        conn.execute('CREATE INDEX IF NOT EXISTS idx_nome_normalizado ON alimentos(nome_normalizado)')
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


def search_taco(food_name: str, threshold: float = 0.4) -> Optional[Dict]:
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
        
        # 2. Busca parcial (LIKE) - termo contido no nome do alimento
        cursor.execute(
            "SELECT * FROM alimentos WHERE nome_normalizado LIKE ? LIMIT 10",
            (f"%{normalized}%",)
        )
        rows = cursor.fetchall()
        
        if rows:
            # Se só tem uma palavra na busca, pegar o primeiro resultado mais simples
            if len(normalized.split()) == 1:
                # Preferir o item mais curto/simples que contém a palavra
                best_match = min(rows, key=lambda r: len(r['nome_normalizado']))
                result = dict(best_match)
                result['match_type'] = 'contains'
                result['match_score'] = 1.0
                result['source'] = 'TACO'
                _taco_cache[normalized] = result
                conn.close()
                return result
            
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
        
        # 3. Busca por palavras-chave (quando tem múltiplas palavras)
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
    Tenta baixar a tabela oficial, se falhar cria tabela básica com alimentos comuns.
    """
    if os.path.exists(TACO_DB_PATH):
        # Verificar se já existe e está válido
        try:
            conn = sqlite3.connect(TACO_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM alimentos")
            count = cursor.fetchone()[0]
            cursor.execute("SELECT updated_at FROM alimentos LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            
            if count > 0 and row:
                updated_at = datetime.fromisoformat(row[0])
                if datetime.now() - updated_at < timedelta(days=30):
                    print(f"Banco TACO está atualizado ({count} alimentos).")
                    return True
        except Exception as e:
            print(f"Erro ao verificar banco TACO: {e}")
    
    # Tentar baixar e converter do Excel
    if convert_xlsx_to_sqlite():
        return True
    
    # Se falhar, criar tabela básica
    print("Criando tabela TACO básica com alimentos brasileiros comuns...")
    return create_basic_taco_table()


def get_taco_stats() -> Dict:
    """Retorna estatísticas do banco TACO."""
    if not os.path.exists(TACO_DB_PATH):
        return {'status': 'not_initialized', 'count': 0}
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        cursor = conn.cursor()
        
        # Verificar se a tabela existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alimentos'")
        if not cursor.fetchone():
            conn.close()
            return {'status': 'not_initialized', 'count': 0}
        
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


# ============================================================
# CACHE LOCAL PARA OPEN FOOD FACTS
# Armazena até 1500 itens consultados para evitar chamadas
# repetidas à API externa
# ============================================================

OFF_CACHE_LIMIT = 1500  # Limite máximo de itens no cache
_off_cache: Dict[str, Dict] = {}  # Cache em memória


def init_off_cache_table() -> bool:
    """
    Inicializa a tabela de cache do Open Food Facts no banco caloria.db.
    Retorna True se a tabela foi criada/existe.
    """
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        cursor = conn.cursor()
        
        # Criar tabela de cache se não existir
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS off_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_busca TEXT UNIQUE,
                nome_produto TEXT,
                marca TEXT,
                codigo_barras TEXT,
                calorias REAL,
                proteina REAL,
                gordura_total REAL,
                gordura_saturada REAL,
                carboidratos REAL,
                acucar REAL,
                fibra REAL,
                sodio REAL,
                potassio REAL,
                colesterol REAL,
                created_at TEXT,
                hits INTEGER DEFAULT 1
            )
        ''')
        
        # Criar índice para busca rápida
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_off_nome ON off_cache(nome_busca)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_off_barcode ON off_cache(codigo_barras)')
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Erro ao criar tabela de cache OFF: {e}")
        return False


def get_off_cache_count() -> int:
    """Retorna o número de itens no cache do Open Food Facts."""
    if not os.path.exists(TACO_DB_PATH):
        return 0
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        cursor = conn.cursor()
        
        # Verificar se a tabela existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='off_cache'")
        if not cursor.fetchone():
            conn.close()
            return 0
        
        cursor.execute("SELECT COUNT(*) FROM off_cache")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


def search_off_cache(food_name: Optional[str] = None, barcode: Optional[str] = None) -> Optional[Dict]:
    """
    Busca um alimento no cache local do Open Food Facts.
    
    Args:
        food_name: Nome do alimento a buscar
        barcode: Código de barras (tem prioridade)
    
    Returns:
        Dicionário com dados nutricionais ou None se não encontrado
    """
    global _off_cache
    
    # Verificar cache em memória primeiro
    cache_key = barcode if barcode else normalize_food_name(food_name) if food_name else None
    if cache_key is not None and cache_key in _off_cache:
        return _off_cache[cache_key]
    
    if not os.path.exists(TACO_DB_PATH):
        return None
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Verificar se a tabela existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='off_cache'")
        if not cursor.fetchone():
            conn.close()
            return None
        
        row = None
        
        # Buscar por código de barras primeiro
        if barcode:
            cursor.execute(
                "SELECT * FROM off_cache WHERE codigo_barras = ? LIMIT 1",
                (barcode,)
            )
            row = cursor.fetchone()
        
        # Se não encontrou por barcode, buscar por nome
        if not row and food_name:
            normalized = normalize_food_name(food_name)
            
            # Busca exata
            cursor.execute(
                "SELECT * FROM off_cache WHERE nome_busca = ? LIMIT 1",
                (normalized,)
            )
            row = cursor.fetchone()
            
            # Busca parcial se não encontrou
            if not row:
                cursor.execute(
                    "SELECT * FROM off_cache WHERE nome_busca LIKE ? ORDER BY hits DESC LIMIT 1",
                    (f"%{normalized}%",)
                )
                row = cursor.fetchone()
        
        if row:
            # Incrementar contador de hits
            cursor.execute(
                "UPDATE off_cache SET hits = hits + 1 WHERE id = ?",
                (row['id'],)
            )
            conn.commit()
            
            result = {
                'name': row['nome_produto'],
                'brand': row['marca'] or '',
                'barcode': row['codigo_barras'] or '',
                'calories': float(row['calorias'] or 0),
                'protein': float(row['proteina'] or 0),
                'fat_total': float(row['gordura_total'] or 0),
                'fat_saturated': float(row['gordura_saturada'] or 0),
                'carbs': float(row['carboidratos'] or 0),
                'sugar': float(row['acucar'] or 0),
                'fiber': float(row['fibra'] or 0),
                'sodium': float(row['sodio'] or 0),
                'potassium': float(row['potassio'] or 0),
                'cholesterol': float(row['colesterol'] or 0),
                'source': 'Open Food Facts (cache)',
                'cached': True
            }
            
            # Salvar no cache em memória
            if cache_key is not None:
                _off_cache[cache_key] = result
            
            conn.close()
            return result
        
        conn.close()
        return None
        
    except Exception as e:
        print(f"Erro ao buscar no cache OFF: {e}")
        return None


def save_to_off_cache(food_name: str, nutrition_data: Dict, barcode: Optional[str] = None) -> bool:
    """
    Salva um alimento no cache local do Open Food Facts.
    Respeita o limite de 1500 itens.
    
    Args:
        food_name: Nome usado na busca
        nutrition_data: Dados nutricionais retornados pela API
        barcode: Código de barras (opcional)
    
    Returns:
        True se salvou com sucesso
    """
    # Verificar se já atingiu o limite
    current_count = get_off_cache_count()
    if current_count >= OFF_CACHE_LIMIT:
        print(f"Cache OFF atingiu limite de {OFF_CACHE_LIMIT} itens. Não salvando.")
        return False
    
    # Inicializar tabela se necessário
    init_off_cache_table()
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        cursor = conn.cursor()
        
        normalized = normalize_food_name(food_name)
        now = datetime.now().isoformat()
        
        # Verificar se já existe
        cursor.execute(
            "SELECT id FROM off_cache WHERE nome_busca = ? OR (codigo_barras = ? AND codigo_barras IS NOT NULL AND codigo_barras != '')",
            (normalized, barcode or '')
        )
        existing = cursor.fetchone()
        
        if existing:
            # Atualizar registro existente
            cursor.execute('''
                UPDATE off_cache SET
                    nome_produto = ?,
                    marca = ?,
                    calorias = ?,
                    proteina = ?,
                    gordura_total = ?,
                    gordura_saturada = ?,
                    carboidratos = ?,
                    acucar = ?,
                    fibra = ?,
                    sodio = ?,
                    potassio = ?,
                    colesterol = ?,
                    hits = hits + 1
                WHERE id = ?
            ''', (
                nutrition_data.get('name', food_name),
                nutrition_data.get('brand', ''),
                nutrition_data.get('calories', 0),
                nutrition_data.get('protein', 0),
                nutrition_data.get('fat_total', 0),
                nutrition_data.get('fat_saturated', 0),
                nutrition_data.get('carbs', 0),
                nutrition_data.get('sugar', 0),
                nutrition_data.get('fiber', 0),
                nutrition_data.get('sodium', 0),
                nutrition_data.get('potassium', 0),
                nutrition_data.get('cholesterol', 0),
                existing[0]
            ))
        else:
            # Inserir novo registro
            cursor.execute('''
                INSERT INTO off_cache (
                    nome_busca, nome_produto, marca, codigo_barras,
                    calorias, proteina, gordura_total, gordura_saturada,
                    carboidratos, acucar, fibra, sodio, potassio, colesterol,
                    created_at, hits
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (
                normalized,
                nutrition_data.get('name', food_name),
                nutrition_data.get('brand', ''),
                barcode or '',
                nutrition_data.get('calories', 0),
                nutrition_data.get('protein', 0),
                nutrition_data.get('fat_total', 0),
                nutrition_data.get('fat_saturated', 0),
                nutrition_data.get('carbs', 0),
                nutrition_data.get('sugar', 0),
                nutrition_data.get('fiber', 0),
                nutrition_data.get('sodium', 0),
                nutrition_data.get('potassium', 0),
                nutrition_data.get('cholesterol', 0),
                now
            ))
            print(f"✅ Salvo no cache OFF: {nutrition_data.get('name', food_name)} ({current_count + 1}/{OFF_CACHE_LIMIT})")
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Erro ao salvar no cache OFF: {e}")
        return False


def get_off_cache_stats() -> Dict:
    """Retorna estatísticas do cache do Open Food Facts."""
    if not os.path.exists(TACO_DB_PATH):
        return {'status': 'not_initialized', 'count': 0, 'limit': OFF_CACHE_LIMIT}
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        cursor = conn.cursor()
        
        # Verificar se a tabela existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='off_cache'")
        if not cursor.fetchone():
            conn.close()
            return {'status': 'not_initialized', 'count': 0, 'limit': OFF_CACHE_LIMIT}
        
        cursor.execute("SELECT COUNT(*) FROM off_cache")
        count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(hits) FROM off_cache")
        total_hits = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT nome_produto, hits FROM off_cache ORDER BY hits DESC LIMIT 5")
        top_items = [(row[0], row[1]) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'status': 'ready',
            'count': count,
            'limit': OFF_CACHE_LIMIT,
            'percentage': round(count / OFF_CACHE_LIMIT * 100, 1),
            'total_hits': total_hits,
            'top_items': top_items
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e), 'limit': OFF_CACHE_LIMIT}


def clear_off_cache() -> bool:
    """Limpa todo o cache do Open Food Facts."""
    global _off_cache
    _off_cache = {}
    
    if not os.path.exists(TACO_DB_PATH):
        return True
    
    try:
        conn = sqlite3.connect(TACO_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM off_cache")
        conn.commit()
        conn.close()
        print("Cache OFF limpo com sucesso.")
        return True
    except Exception as e:
        print(f"Erro ao limpar cache OFF: {e}")
        return False
