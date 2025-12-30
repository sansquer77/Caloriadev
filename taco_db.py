"""
# TODO: Atualizar create_basic_taco_table() com 596 alimentos da TACO 4ª edição (arquivo taco-4a-edicao)
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
        {"nome": "Arroz, integral, cozido", "calorias": 123.5, "proteina": 2.6, "gordura_total": 1.0, "carboidratos": 25.8, "fibra": 2.7, "sodio": 1.2},
        {"nome": "Arroz, integral, cru", "calorias": 359.7, "proteina": 7.3, "gordura_total": 1.9, "carboidratos": 77.5, "fibra": 4.8, "sodio": 1.6},
        {"nome": "Arroz, tipo 1, cozido", "calorias": 128.3, "proteina": 2.5, "gordura_total": 0.2, "carboidratos": 28.1, "fibra": 1.6, "sodio": 1.2},
        {"nome": "Arroz, tipo 1, cru", "calorias": 357.8, "proteina": 7.2, "gordura_total": 0.3, "carboidratos": 78.8, "fibra": 1.6, "sodio": 1.0},
        {"nome": "Arroz, tipo 2, cozido", "calorias": 130.1, "proteina": 2.6, "gordura_total": 0.4, "carboidratos": 28.2, "fibra": 1.1, "sodio": 2.0},
        {"nome": "Arroz, tipo 2, cru", "calorias": 358.1, "proteina": 7.2, "gordura_total": 0.3, "carboidratos": 78.9, "fibra": 1.7, "sodio": 0.6},
        {"nome": "Aveia, flocos, crua", "calorias": 393.8, "proteina": 13.9, "gordura_total": 8.5, "carboidratos": 66.6, "fibra": 9.1, "sodio": 4.6},
        {"nome": "Biscoito, doce, maisena", "calorias": 442.8, "proteina": 8.1, "gordura_total": 12.0, "carboidratos": 75.2, "fibra": 2.1, "sodio": 352.0},
        {"nome": "Biscoito, doce, recheado com chocolate", "calorias": 471.8, "proteina": 6.4, "gordura_total": 19.6, "carboidratos": 70.5, "fibra": 3.0, "sodio": 239.2},
        {"nome": "Biscoito, doce, recheado com morango", "calorias": 471.2, "proteina": 5.7, "gordura_total": 19.6, "carboidratos": 71.0, "fibra": 1.5, "sodio": 229.8},
        {"nome": "Biscoito, doce, wafer, recheado de chocolate", "calorias": 502.5, "proteina": 5.6, "gordura_total": 24.7, "carboidratos": 67.5, "fibra": 1.8, "sodio": 137.2},
        {"nome": "Biscoito, doce, wafer, recheado de morango", "calorias": 513.4, "proteina": 4.5, "gordura_total": 26.4, "carboidratos": 67.4, "fibra": 0.8, "sodio": 119.9},
        {"nome": "Biscoito, salgado, cream cracker", "calorias": 431.7, "proteina": 10.1, "gordura_total": 14.4, "carboidratos": 68.7, "fibra": 2.5, "sodio": 854.4},
        {"nome": "Bolo, mistura para", "calorias": 418.6, "proteina": 6.2, "gordura_total": 6.1, "carboidratos": 84.7, "fibra": 1.7, "sodio": 462.9},
        {"nome": "Bolo, pronto, aipim", "calorias": 323.9, "proteina": 4.4, "gordura_total": 12.7, "carboidratos": 47.9, "fibra": 0.7, "sodio": 111.0},
        {"nome": "Bolo, pronto, chocolate", "calorias": 410.0, "proteina": 6.2, "gordura_total": 18.5, "carboidratos": 54.7, "fibra": 1.4, "sodio": 283.3},
        {"nome": "Bolo, pronto, coco", "calorias": 333.4, "proteina": 5.7, "gordura_total": 11.3, "carboidratos": 52.3, "fibra": 1.1, "sodio": 190.3},
        {"nome": "Bolo, pronto, milho", "calorias": 311.4, "proteina": 4.8, "gordura_total": 12.4, "carboidratos": 45.1, "fibra": 0.7, "sodio": 133.8},
        {"nome": "Canjica, branca, crua", "calorias": 357.6, "proteina": 7.2, "gordura_total": 1.0, "carboidratos": 78.1, "fibra": 5.5, "sodio": 0.8},
        {"nome": "Cereal matinal, milho", "calorias": 365.4, "proteina": 7.2, "gordura_total": 1.0, "carboidratos": 83.8, "fibra": 4.1, "sodio": 654.5},
        {"nome": "Cereal matinal, milho, açúcar", "calorias": 376.6, "proteina": 4.7, "gordura_total": 0.7, "carboidratos": 88.8, "fibra": 2.1, "sodio": 405.3},
        {"nome": "Creme de arroz, pó", "calorias": 386.0, "proteina": 7.0, "gordura_total": 1.2, "carboidratos": 83.9, "fibra": 1.1, "sodio": 1.0},
        {"nome": "Creme de milho, pó", "calorias": 333.0, "proteina": 4.8, "gordura_total": 1.6, "carboidratos": 86.1, "fibra": 3.7, "sodio": 593.8},
        {"nome": "Curau, milho verde", "calorias": 78.4, "proteina": 2.4, "gordura_total": 1.6, "carboidratos": 13.9, "fibra": 0.5, "sodio": 20.5},
        {"nome": "Curau, milho verde, mistura para", "calorias": 402.3, "proteina": 2.2, "gordura_total": 13.4, "carboidratos": 79.8, "fibra": 2.5, "sodio": 222.9},
        {"nome": "Farinha, de arroz, enriquecida", "calorias": 363.1, "proteina": 1.3, "gordura_total": 0.3, "carboidratos": 85.5, "fibra": 0.6, "sodio": 17.1},
        {"nome": "Farinha, de centeio, integral", "calorias": 335.8, "proteina": 12.5, "gordura_total": 1.8, "carboidratos": 73.3, "fibra": 15.5, "sodio": 41.4},
        {"nome": "Farinha, de milho, amarela", "calorias": 350.6, "proteina": 7.2, "gordura_total": 1.5, "carboidratos": 79.1, "fibra": 5.5, "sodio": 44.9},
        {"nome": "Farinha, de rosca", "calorias": 370.6, "proteina": 11.4, "gordura_total": 1.5, "carboidratos": 75.8, "fibra": 4.8, "sodio": 332.5},
        {"nome": "Farinha, de trigo", "calorias": 360.5, "proteina": 9.8, "gordura_total": 1.4, "carboidratos": 75.1, "fibra": 2.3, "sodio": 0.7},
        {"nome": "Lasanha, massa fresca, cozida", "calorias": 163.8, "proteina": 5.8, "gordura_total": 1.2, "carboidratos": 32.5, "fibra": 1.6, "sodio": 206.8},
        {"nome": "Lasanha, massa fresca, crua", "calorias": 220.3, "proteina": 7.0, "gordura_total": 1.3, "carboidratos": 45.1, "fibra": 1.6, "sodio": 666.7},
        {"nome": "Macarrão, instantâneo", "calorias": 435.9, "proteina": 8.8, "gordura_total": 17.2, "carboidratos": 62.4, "fibra": 5.6, "sodio": 1515.5},
        {"nome": "Macarrão, trigo, cru", "calorias": 371.1, "proteina": 10.0, "gordura_total": 1.3, "carboidratos": 77.9, "fibra": 2.9, "sodio": 7.2},
        {"nome": "Milho, amido, cru", "calorias": 361.4, "proteina": 0.6, "gordura_total": 0, "carboidratos": 87.1, "fibra": 0.7, "sodio": 8.1},
        {"nome": "Milho, fubá, cru", "calorias": 353.5, "proteina": 7.2, "gordura_total": 1.9, "carboidratos": 78.9, "fibra": 4.7, "sodio": 0},
        {"nome": "Milho, verde, cru", "calorias": 138.2, "proteina": 6.6, "gordura_total": 0.6, "carboidratos": 28.6, "fibra": 3.9, "sodio": 1.1},
        {"nome": "Milho, verde, enlatado, drenado", "calorias": 97.6, "proteina": 3.2, "gordura_total": 2.4, "carboidratos": 17.1, "fibra": 4.6, "sodio": 260.3},
        {"nome": "Mingau tradicional, pó", "calorias": 373.4, "proteina": 0.6, "gordura_total": 0.4, "carboidratos": 89.3, "fibra": 0.9, "sodio": 14.9},
        {"nome": "Pamonha, barra para cozimento, pré-cozida", "calorias": 171.2, "proteina": 2.6, "gordura_total": 4.8, "carboidratos": 30.7, "fibra": 2.4, "sodio": 132.0},
        {"nome": "Pão, aveia, forma", "calorias": 343.1, "proteina": 12.3, "gordura_total": 5.7, "carboidratos": 59.6, "fibra": 6.0, "sodio": 605.8},
        {"nome": "Pão, de soja", "calorias": 308.7, "proteina": 11.3, "gordura_total": 3.6, "carboidratos": 56.5, "fibra": 5.7, "sodio": 662.5},
        {"nome": "Pão, glúten, forma", "calorias": 253.0, "proteina": 12.0, "gordura_total": 2.7, "carboidratos": 44.1, "fibra": 2.5, "sodio": 22.0},
        {"nome": "Pão, milho, forma", "calorias": 292.0, "proteina": 8.3, "gordura_total": 3.1, "carboidratos": 56.4, "fibra": 4.3, "sodio": 506.6},
        {"nome": "Pão, trigo, forma, integral", "calorias": 253.2, "proteina": 9.4, "gordura_total": 3.7, "carboidratos": 49.9, "fibra": 6.9, "sodio": 506.1},
        {"nome": "Pão, trigo, francês", "calorias": 299.8, "proteina": 8.0, "gordura_total": 3.1, "carboidratos": 58.6, "fibra": 2.3, "sodio": 647.7},
        {"nome": "Pão, trigo, sovado", "calorias": 311.0, "proteina": 8.4, "gordura_total": 2.8, "carboidratos": 61.5, "fibra": 2.4, "sodio": 430.8},
        {"nome": "Pastel, de carne, cru", "calorias": 288.7, "proteina": 10.7, "gordura_total": 8.8, "carboidratos": 42.0, "fibra": 1.0, "sodio": 1309.3},
        {"nome": "Pastel, de carne, frito", "calorias": 388.4, "proteina": 10.1, "gordura_total": 20.1, "carboidratos": 43.8, "fibra": 1.0, "sodio": 1039.9},
        {"nome": "Pastel, de queijo, cru", "calorias": 308.5, "proteina": 9.9, "gordura_total": 9.6, "carboidratos": 45.9, "fibra": 1.1, "sodio": 984.6},
        {"nome": "Pastel, de queijo, frito", "calorias": 422.1, "proteina": 8.7, "gordura_total": 22.7, "carboidratos": 48.1, "fibra": 0.9, "sodio": 821.4},
        {"nome": "Pastel, massa, crua", "calorias": 310.2, "proteina": 6.9, "gordura_total": 5.5, "carboidratos": 57.4, "fibra": 1.4, "sodio": 1344.2},
        {"nome": "Pastel, massa, frita", "calorias": 569.7, "proteina": 6.0, "gordura_total": 40.9, "carboidratos": 49.3, "fibra": 1.3, "sodio": 1174.7},
        {"nome": "Pipoca, com óleo de soja, sem sal", "calorias": 448.3, "proteina": 9.9, "gordura_total": 15.9, "carboidratos": 70.3, "fibra": 14.3, "sodio": 4.3},
        {"nome": "Polenta, pré-cozida", "calorias": 102.7, "proteina": 2.3, "gordura_total": 0.3, "carboidratos": 23.3, "fibra": 2.4, "sodio": 441.9},
        {"nome": "Torrada, pão francês", "calorias": 377.4, "proteina": 10.5, "gordura_total": 3.3, "carboidratos": 74.6, "fibra": 3.4, "sodio": 829.5},
        {"nome": "Abóbora, cabotian, cozida", "calorias": 48.0, "proteina": 1.4, "gordura_total": 0.7, "carboidratos": 10.8, "fibra": 2.5, "sodio": 1.5},
        {"nome": "Abóbora, cabotian, crua", "calorias": 38.6, "proteina": 1.7, "gordura_total": 0.5, "carboidratos": 8.4, "fibra": 2.2, "sodio": 0},
        {"nome": "Abóbora, menina brasileira, crua", "calorias": 13.6, "proteina": 0.6, "gordura_total": 0, "carboidratos": 3.3, "fibra": 1.2, "sodio": 0},
        {"nome": "Abóbora, moranga, crua", "calorias": 12.4, "proteina": 1.0, "gordura_total": 0.1, "carboidratos": 2.7, "fibra": 1.7, "sodio": 0},
        {"nome": "Abóbora, moranga, refogada", "calorias": 29.0, "proteina": 0.4, "gordura_total": 0.8, "carboidratos": 6.0, "fibra": 1.5, "sodio": 3.0},
        {"nome": "Abóbora, pescoço, crua", "calorias": 24.5, "proteina": 0.7, "gordura_total": 0.1, "carboidratos": 6.1, "fibra": 2.3, "sodio": 0.7},
        {"nome": "Abobrinha, italiana, cozida", "calorias": 15.0, "proteina": 1.1, "gordura_total": 0.2, "carboidratos": 3.0, "fibra": 1.6, "sodio": 0.8},
        {"nome": "Abobrinha, italiana, crua", "calorias": 19.3, "proteina": 1.1, "gordura_total": 0.1, "carboidratos": 4.3, "fibra": 1.4, "sodio": 0},
        {"nome": "Abobrinha, italiana, refogada", "calorias": 24.4, "proteina": 1.1, "gordura_total": 0.8, "carboidratos": 4.2, "fibra": 1.4, "sodio": 2.2},
        {"nome": "Abobrinha, paulista, crua", "calorias": 30.8, "proteina": 0.6, "gordura_total": 0.1, "carboidratos": 7.9, "fibra": 2.6, "sodio": 0.5},
        {"nome": "Acelga, crua", "calorias": 20.9, "proteina": 1.4, "gordura_total": 0.1, "carboidratos": 4.6, "fibra": 1.1, "sodio": 1.2},
        {"nome": "Agrião, cru", "calorias": 16.6, "proteina": 2.7, "gordura_total": 0.2, "carboidratos": 2.3, "fibra": 2.1, "sodio": 7.5},
        {"nome": "Aipo, cru", "calorias": 19.1, "proteina": 0.8, "gordura_total": 0.1, "carboidratos": 4.3, "fibra": 1.0, "sodio": 9.5},
        {"nome": "Alface, americana, crua", "calorias": 8.8, "proteina": 0.6, "gordura_total": 0.1, "carboidratos": 1.7, "fibra": 1.0, "sodio": 7.3},
        {"nome": "Alface, crespa, crua", "calorias": 10.7, "proteina": 1.3, "gordura_total": 0.2, "carboidratos": 1.7, "fibra": 1.8, "sodio": 3.4},
        {"nome": "Alface, lisa, crua", "calorias": 13.8, "proteina": 1.7, "gordura_total": 0.1, "carboidratos": 2.4, "fibra": 2.3, "sodio": 4.2},
        {"nome": "Alface, roxa, crua", "calorias": 12.7, "proteina": 0.9, "gordura_total": 0.2, "carboidratos": 2.5, "fibra": 2.0, "sodio": 7.1},
        {"nome": "Alfavaca, crua", "calorias": 29.2, "proteina": 2.7, "gordura_total": 0.5, "carboidratos": 5.2, "fibra": 4.1, "sodio": 4.6},
        {"nome": "Alho, cru", "calorias": 113.1, "proteina": 7.0, "gordura_total": 0.2, "carboidratos": 23.9, "fibra": 4.3, "sodio": 5.4},
        {"nome": "Alho-poró, cru", "calorias": 31.5, "proteina": 1.4, "gordura_total": 0.1, "carboidratos": 6.9, "fibra": 2.5, "sodio": 1.8},
        {"nome": "Almeirão, cru", "calorias": 18.0, "proteina": 1.8, "gordura_total": 0.2, "carboidratos": 3.3, "fibra": 2.6, "sodio": 2.4},
        {"nome": "Almeirão, refogado", "calorias": 65.1, "proteina": 1.7, "gordura_total": 4.8, "carboidratos": 5.7, "fibra": 3.4, "sodio": 14.5},
        {"nome": "Batata, baroa, cozida", "calorias": 80.1, "proteina": 0.9, "gordura_total": 0.2, "carboidratos": 18.9, "fibra": 1.8, "sodio": 2.1},
        {"nome": "Batata, baroa, crua", "calorias": 101.0, "proteina": 1.0, "gordura_total": 0.2, "carboidratos": 24.0, "fibra": 2.1, "sodio": 0},
        {"nome": "Batata, doce, cozida", "calorias": 76.8, "proteina": 0.6, "gordura_total": 0.1, "carboidratos": 18.4, "fibra": 2.2, "sodio": 2.7},
        {"nome": "Batata, doce, crua", "calorias": 118.2, "proteina": 1.3, "gordura_total": 0.1, "carboidratos": 28.2, "fibra": 2.6, "sodio": 8.8},
        {"nome": "Batata, frita, tipo chips, industrializada", "calorias": 542.7, "proteina": 5.6, "gordura_total": 36.6, "carboidratos": 51.2, "fibra": 2.5, "sodio": 607.4},
        {"nome": "Batata, inglesa, cozida", "calorias": 51.6, "proteina": 1.2, "gordura_total": 0, "carboidratos": 11.9, "fibra": 1.3, "sodio": 2.3},
        {"nome": "Batata, inglesa, crua", "calorias": 64.4, "proteina": 1.8, "gordura_total": 0, "carboidratos": 14.7, "fibra": 1.2, "sodio": 0},
        {"nome": "Batata, inglesa, frita", "calorias": 267.2, "proteina": 5.0, "gordura_total": 13.1, "carboidratos": 35.6, "fibra": 8.1, "sodio": 1.9},
        {"nome": "Batata, inglesa, sauté", "calorias": 67.9, "proteina": 1.3, "gordura_total": 0.9, "carboidratos": 14.1, "fibra": 1.4, "sodio": 8.2},
        {"nome": "Berinjela, cozida", "calorias": 18.8, "proteina": 0.7, "gordura_total": 0.1, "carboidratos": 4.5, "fibra": 2.5, "sodio": 1.3},
        {"nome": "Berinjela, crua", "calorias": 19.6, "proteina": 1.2, "gordura_total": 0.1, "carboidratos": 4.4, "fibra": 2.9, "sodio": 0},
        {"nome": "Beterraba, cozida", "calorias": 32.2, "proteina": 1.3, "gordura_total": 0.1, "carboidratos": 7.2, "fibra": 1.9, "sodio": 22.8},
        {"nome": "Beterraba, crua", "calorias": 48.8, "proteina": 1.9, "gordura_total": 0.1, "carboidratos": 11.1, "fibra": 3.4, "sodio": 9.7},
        {"nome": "Biscoito, polvilho doce", "calorias": 437.5, "proteina": 1.3, "gordura_total": 12.2, "carboidratos": 80.5, "fibra": 1.2, "sodio": 97.8},
        {"nome": "Brócolis, cozido", "calorias": 24.6, "proteina": 2.1, "gordura_total": 0.5, "carboidratos": 4.4, "fibra": 3.4, "sodio": 2.1},
        {"nome": "Brócolis, cru", "calorias": 25.5, "proteina": 3.6, "gordura_total": 0.3, "carboidratos": 4.0, "fibra": 2.9, "sodio": 3.3},
        {"nome": "Cará, cozido", "calorias": 77.6, "proteina": 1.5, "gordura_total": 0.1, "carboidratos": 18.9, "fibra": 2.6, "sodio": 1.0},
        {"nome": "Cará, cru", "calorias": 95.6, "proteina": 2.3, "gordura_total": 0.1, "carboidratos": 23.0, "fibra": 7.3, "sodio": 0},
        {"nome": "Caruru, cru", "calorias": 34.0, "proteina": 3.2, "gordura_total": 0.6, "carboidratos": 6.0, "fibra": 4.5, "sodio": 13.7},
        {"nome": "Catalonha, crua", "calorias": 23.9, "proteina": 1.9, "gordura_total": 0.3, "carboidratos": 4.8, "fibra": 2.0, "sodio": 9.4},
        {"nome": "Catalonha, refogada", "calorias": 63.4, "proteina": 1.9, "gordura_total": 4.8, "carboidratos": 4.8, "fibra": 3.6, "sodio": 24.7},
        {"nome": "Cebola, crua", "calorias": 39.4, "proteina": 1.7, "gordura_total": 0.1, "carboidratos": 8.9, "fibra": 2.2, "sodio": 0.6},
        {"nome": "Cebolinha, crua", "calorias": 19.5, "proteina": 1.9, "gordura_total": 0.3, "carboidratos": 3.4, "fibra": 3.5, "sodio": 1.6},
        {"nome": "Cenoura, cozida", "calorias": 29.9, "proteina": 0.8, "gordura_total": 0.2, "carboidratos": 6.7, "fibra": 2.6, "sodio": 7.9},
        {"nome": "Cenoura, crua", "calorias": 34.1, "proteina": 1.3, "gordura_total": 0.2, "carboidratos": 7.7, "fibra": 3.2, "sodio": 3.3},
        {"nome": "Chicória, crua", "calorias": 13.8, "proteina": 1.1, "gordura_total": 0.1, "carboidratos": 2.9, "fibra": 2.2, "sodio": 13.5},
        {"nome": "Chuchu, cozido", "calorias": 18.5, "proteina": 0.4, "gordura_total": 0, "carboidratos": 4.8, "fibra": 1.0, "sodio": 1.8},
        {"nome": "Chuchu, cru", "calorias": 17.0, "proteina": 0.7, "gordura_total": 0.1, "carboidratos": 4.1, "fibra": 1.3, "sodio": 0},
        {"nome": "Coentro, folhas desidratadas", "calorias": 309.1, "proteina": 20.9, "gordura_total": 10.4, "carboidratos": 48.0, "fibra": 37.3, "sodio": 18.3},
        {"nome": "Couve, manteiga, crua", "calorias": 27.1, "proteina": 2.9, "gordura_total": 0.5, "carboidratos": 4.3, "fibra": 3.1, "sodio": 6.2},
        {"nome": "Couve, manteiga, refogada", "calorias": 90.3, "proteina": 1.7, "gordura_total": 6.6, "carboidratos": 8.7, "fibra": 5.7, "sodio": 11.4},
        {"nome": "Couve-flor, crua", "calorias": 22.6, "proteina": 1.9, "gordura_total": 0.2, "carboidratos": 4.5, "fibra": 2.4, "sodio": 3.4},
        {"nome": "Couve-flor, cozida", "calorias": 19.1, "proteina": 1.2, "gordura_total": 0.3, "carboidratos": 3.9, "fibra": 2.1, "sodio": 1.8},
        {"nome": "Espinafre, Nova Zelândia, cru", "calorias": 16.1, "proteina": 2.0, "gordura_total": 0.2, "carboidratos": 2.6, "fibra": 2.1, "sodio": 17.1},
        {"nome": "Espinafre, Nova Zelândia, refogado", "calorias": 67.3, "proteina": 2.7, "gordura_total": 5.4, "carboidratos": 4.2, "fibra": 2.5, "sodio": 47.0},
        {"nome": "Farinha, de mandioca, crua", "calorias": 360.9, "proteina": 1.6, "gordura_total": 0.3, "carboidratos": 87.9, "fibra": 6.4, "sodio": 1.0},
        {"nome": "Farinha, de mandioca, torrada", "calorias": 365.3, "proteina": 1.2, "gordura_total": 0.3, "carboidratos": 89.2, "fibra": 6.5, "sodio": 10.3},
        {"nome": "Farinha, de puba", "calorias": 360.2, "proteina": 1.6, "gordura_total": 0.5, "carboidratos": 87.3, "fibra": 4.2, "sodio": 3.6},
        {"nome": "Fécula, de mandioca", "calorias": 330.9, "proteina": 0.5, "gordura_total": 0.3, "carboidratos": 81.1, "fibra": 0.6, "sodio": 2.4},
        {"nome": "Feijão, broto, cru", "calorias": 38.7, "proteina": 4.2, "gordura_total": 0.1, "carboidratos": 7.8, "fibra": 2.0, "sodio": 1.8},
        {"nome": "Inhame, cru", "calorias": 96.7, "proteina": 2.1, "gordura_total": 0.2, "carboidratos": 23.2, "fibra": 1.7, "sodio": 0},
        {"nome": "Jiló, cru", "calorias": 27.4, "proteina": 1.4, "gordura_total": 0.2, "carboidratos": 6.2, "fibra": 4.8, "sodio": 0},
        {"nome": "Jurubeba, crua", "calorias": 125.8, "proteina": 4.4, "gordura_total": 3.9, "carboidratos": 23.1, "fibra": 23.9, "sodio": 0.8},
        {"nome": "Mandioca, cozida", "calorias": 125.4, "proteina": 0.6, "gordura_total": 0.3, "carboidratos": 30.1, "fibra": 1.6, "sodio": 0.9},
        {"nome": "Mandioca, crua", "calorias": 151.4, "proteina": 1.1, "gordura_total": 0.3, "carboidratos": 36.2, "fibra": 1.9, "sodio": 2.1},
        {"nome": "Mandioca, farofa, temperada", "calorias": 405.7, "proteina": 2.1, "gordura_total": 9.1, "carboidratos": 80.3, "fibra": 7.8, "sodio": 574.5},
        {"nome": "Mandioca, frita", "calorias": 300.1, "proteina": 1.4, "gordura_total": 11.2, "carboidratos": 50.3, "fibra": 1.9, "sodio": 8.9},
        {"nome": "Manjericão, cru", "calorias": 21.1, "proteina": 2.0, "gordura_total": 0.4, "carboidratos": 3.6, "fibra": 3.3, "sodio": 3.9},
        {"nome": "Maxixe, cru", "calorias": 13.7, "proteina": 1.4, "gordura_total": 0.1, "carboidratos": 2.7, "fibra": 2.2, "sodio": 11.0},
        {"nome": "Mostarda, folha, crua", "calorias": 18.1, "proteina": 2.1, "gordura_total": 0.2, "carboidratos": 3.2, "fibra": 1.9, "sodio": 2.9},
        {"nome": "Nhoque, batata, cozido", "calorias": 180.8, "proteina": 5.9, "gordura_total": 1.9, "carboidratos": 36.8, "fibra": 1.8, "sodio": 7.1},
        {"nome": "Nabo, cru", "calorias": 18.2, "proteina": 1.2, "gordura_total": 0.1, "carboidratos": 4.1, "fibra": 2.6, "sodio": 2.5},
        {"nome": "Palmito, juçara, em conserva", "calorias": 23.2, "proteina": 1.8, "gordura_total": 0.4, "carboidratos": 4.3, "fibra": 3.1, "sodio": 513.8},
        {"nome": "Palmito, pupunha, em conserva", "calorias": 29.4, "proteina": 2.5, "gordura_total": 0.5, "carboidratos": 5.5, "fibra": 2.5, "sodio": 562.7},
        {"nome": "Pão, de queijo, assado", "calorias": 363.1, "proteina": 5.1, "gordura_total": 24.6, "carboidratos": 34.2, "fibra": 0.6, "sodio": 773.5},
        {"nome": "Pão, de queijo, cru", "calorias": 294.5, "proteina": 3.6, "gordura_total": 14.0, "carboidratos": 38.5, "fibra": 1.0, "sodio": 405.0},
        {"nome": "Pepino, cru", "calorias": 9.5, "proteina": 0.9, "gordura_total": 0, "carboidratos": 2.0, "fibra": 1.1, "sodio": 0},
        {"nome": "Pimentão, amarelo, cru", "calorias": 27.9, "proteina": 1.2, "gordura_total": 0.4, "carboidratos": 6.0, "fibra": 1.9, "sodio": 0},
        {"nome": "Pimentão, verde, cru", "calorias": 21.3, "proteina": 1.1, "gordura_total": 0.1, "carboidratos": 4.9, "fibra": 2.6, "sodio": 0},
        {"nome": "Pimentão, vermelho, cru", "calorias": 23.3, "proteina": 1.0, "gordura_total": 0.1, "carboidratos": 5.5, "fibra": 1.6, "sodio": 0},
        {"nome": "Polvilho, doce", "calorias": 351.2, "proteina": 0.4, "gordura_total": 0, "carboidratos": 86.8, "fibra": 0.2, "sodio": 1.6},
        {"nome": "Quiabo, cru", "calorias": 29.9, "proteina": 1.9, "gordura_total": 0.3, "carboidratos": 6.4, "fibra": 4.6, "sodio": 0.9},
        {"nome": "Rabanete, cru", "calorias": 13.7, "proteina": 1.4, "gordura_total": 0.1, "carboidratos": 2.7, "fibra": 2.2, "sodio": 11.0},
        {"nome": "Repolho, branco, cru", "calorias": 17.1, "proteina": 0.9, "gordura_total": 0.1, "carboidratos": 3.9, "fibra": 1.9, "sodio": 3.6},
        {"nome": "Repolho, roxo, cru", "calorias": 30.9, "proteina": 1.9, "gordura_total": 0.1, "carboidratos": 7.2, "fibra": 2.0, "sodio": 2.3},
        {"nome": "Repolho, roxo, refogado", "calorias": 41.8, "proteina": 1.8, "gordura_total": 1.2, "carboidratos": 7.6, "fibra": 1.8, "sodio": 3.4},
        {"nome": "Rúcula, crua", "calorias": 13.1, "proteina": 1.8, "gordura_total": 0.1, "carboidratos": 2.2, "fibra": 1.7, "sodio": 9.4},
        {"nome": "Salsa, crua", "calorias": 33.4, "proteina": 3.3, "gordura_total": 0.6, "carboidratos": 5.7, "fibra": 1.9, "sodio": 2.3},
        {"nome": "Seleta de legumes, enlatada", "calorias": 56.5, "proteina": 3.4, "gordura_total": 0.4, "carboidratos": 12.7, "fibra": 3.1, "sodio": 398.1},
        {"nome": "Serralha, crua", "calorias": 30.4, "proteina": 2.7, "gordura_total": 0.7, "carboidratos": 4.9, "fibra": 3.5, "sodio": 19.3},
        {"nome": "Taioba, crua", "calorias": 34.2, "proteina": 2.9, "gordura_total": 0.9, "carboidratos": 5.4, "fibra": 4.5, "sodio": 1.2},
        {"nome": "Tomate, com semente, cru", "calorias": 15.3, "proteina": 1.1, "gordura_total": 0.2, "carboidratos": 3.1, "fibra": 1.2, "sodio": 1.0},
        {"nome": "Tomate, extrato", "calorias": 60.9, "proteina": 2.4, "gordura_total": 0.2, "carboidratos": 15.0, "fibra": 2.8, "sodio": 497.9},
        {"nome": "Tomate, molho industrializado", "calorias": 38.4, "proteina": 1.4, "gordura_total": 0.9, "carboidratos": 7.7, "fibra": 3.1, "sodio": 418.3},
        {"nome": "Tomate, purê", "calorias": 27.9, "proteina": 1.4, "gordura_total": 0, "carboidratos": 6.9, "fibra": 1.0, "sodio": 103.9},
        {"nome": "Tomate, salada", "calorias": 20.5, "proteina": 0.8, "gordura_total": 0, "carboidratos": 5.1, "fibra": 2.3, "sodio": 5.2},
        {"nome": "Vagem, crua", "calorias": 24.9, "proteina": 1.8, "gordura_total": 0.2, "carboidratos": 5.3, "fibra": 2.4, "sodio": 0},
        {"nome": "Abacate, cru", "calorias": 96.2, "proteina": 1.2, "gordura_total": 8.4, "carboidratos": 6.0, "fibra": 6.3, "sodio": 0},
        {"nome": "Abacaxi, cru", "calorias": 48.3, "proteina": 0.9, "gordura_total": 0.1, "carboidratos": 12.3, "fibra": 1.0, "sodio": 0},
        {"nome": "Abacaxi, polpa, congelada", "calorias": 30.6, "proteina": 0.5, "gordura_total": 0.1, "carboidratos": 7.8, "fibra": 0.3, "sodio": 1.2},
        {"nome": "Abiu, cru", "calorias": 62.4, "proteina": 0.8, "gordura_total": 0.7, "carboidratos": 14.9, "fibra": 1.7, "sodio": 0},
        {"nome": "Açaí, polpa, com xarope de guaraná e glucose", "calorias": 110.3, "proteina": 0.7, "gordura_total": 3.7, "carboidratos": 21.5, "fibra": 1.7, "sodio": 15.1},
        {"nome": "Açaí, polpa, congelada", "calorias": 58.0, "proteina": 0.8, "gordura_total": 3.9, "carboidratos": 6.2, "fibra": 2.6, "sodio": 5.2},
        {"nome": "Acerola, crua", "calorias": 33.5, "proteina": 0.9, "gordura_total": 0.2, "carboidratos": 8.0, "fibra": 1.5, "sodio": 0},
        {"nome": "Acerola, polpa, congelada", "calorias": 21.9, "proteina": 0.6, "gordura_total": 0, "carboidratos": 5.5, "fibra": 0.7, "sodio": 1.3},
        {"nome": "Ameixa, calda, enlatada", "calorias": 182.8, "proteina": 0.4, "gordura_total": 0, "carboidratos": 46.9, "fibra": 0.5, "sodio": 2.7},
        {"nome": "Ameixa, crua", "calorias": 52.5, "proteina": 0.8, "gordura_total": 0, "carboidratos": 13.9, "fibra": 2.4, "sodio": 0},
        {"nome": "Ameixa, em calda, enlatada, drenada", "calorias": 177.4, "proteina": 1.0, "gordura_total": 0.3, "carboidratos": 47.7, "fibra": 4.5, "sodio": 2.8},
        {"nome": "Atemóia, crua", "calorias": 97.0, "proteina": 1.0, "gordura_total": 0.3, "carboidratos": 25.3, "fibra": 2.1, "sodio": 0.8},
        {"nome": "Banana, da terra, crua", "calorias": 128.0, "proteina": 1.4, "gordura_total": 0.2, "carboidratos": 33.7, "fibra": 1.5, "sodio": 0},
        {"nome": "Banana, doce em barra", "calorias": 280.1, "proteina": 2.2, "gordura_total": 0.1, "carboidratos": 75.7, "fibra": 3.8, "sodio": 9.9},
        {"nome": "Banana, figo, crua", "calorias": 105.1, "proteina": 1.1, "gordura_total": 0.1, "carboidratos": 27.8, "fibra": 2.8, "sodio": 0},
        {"nome": "Banana, maçã, crua", "calorias": 86.8, "proteina": 1.8, "gordura_total": 0.1, "carboidratos": 22.3, "fibra": 2.6, "sodio": 0},
        {"nome": "Banana, nanica, crua", "calorias": 91.5, "proteina": 1.4, "gordura_total": 0.1, "carboidratos": 23.8, "fibra": 1.9, "sodio": 0},
        {"nome": "Banana, ouro, crua", "calorias": 112.4, "proteina": 1.5, "gordura_total": 0.2, "carboidratos": 29.3, "fibra": 2.0, "sodio": 0},
        {"nome": "Banana, pacova, crua", "calorias": 77.9, "proteina": 1.2, "gordura_total": 0.1, "carboidratos": 20.3, "fibra": 2.0, "sodio": 0.9},
        {"nome": "Banana, prata, crua", "calorias": 98.2, "proteina": 1.3, "gordura_total": 0.1, "carboidratos": 26.0, "fibra": 2.0, "sodio": 0},
        {"nome": "Cacau, cru", "calorias": 74.3, "proteina": 1.0, "gordura_total": 0.1, "carboidratos": 19.4, "fibra": 2.2, "sodio": 0.7},
        {"nome": "Cajá-Manga, cru", "calorias": 45.6, "proteina": 1.3, "gordura_total": 0, "carboidratos": 11.4, "fibra": 2.6, "sodio": 1.4},
        {"nome": "Cajá, polpa, congelada", "calorias": 26.3, "proteina": 0.6, "gordura_total": 0.2, "carboidratos": 6.4, "fibra": 1.4, "sodio": 6.9},
        {"nome": "Caju, cru", "calorias": 43.1, "proteina": 1.0, "gordura_total": 0.3, "carboidratos": 10.3, "fibra": 1.7, "sodio": 3.0},
        {"nome": "Caju, polpa, congelada", "calorias": 36.6, "proteina": 0.5, "gordura_total": 0.2, "carboidratos": 9.4, "fibra": 0.8, "sodio": 4.2},
        {"nome": "Caju, suco concentrado, envasado", "calorias": 45.1, "proteina": 0.4, "gordura_total": 0.2, "carboidratos": 10.7, "fibra": 0.6, "sodio": 45.0},
        {"nome": "Caqui, chocolate, cru", "calorias": 71.4, "proteina": 0.4, "gordura_total": 0.1, "carboidratos": 19.3, "fibra": 6.5, "sodio": 2.2},
        {"nome": "Carambola, crua", "calorias": 45.7, "proteina": 0.9, "gordura_total": 0.2, "carboidratos": 11.5, "fibra": 2.0, "sodio": 4.1},
        {"nome": "Ciriguela, crua", "calorias": 75.6, "proteina": 1.4, "gordura_total": 0.4, "carboidratos": 18.9, "fibra": 3.9, "sodio": 1.7},
        {"nome": "Cupuaçu, cru", "calorias": 49.4, "proteina": 1.2, "gordura_total": 1.0, "carboidratos": 10.4, "fibra": 3.1, "sodio": 3.2},
        {"nome": "Cupuaçu, polpa, congelada", "calorias": 48.8, "proteina": 0.8, "gordura_total": 0.6, "carboidratos": 11.4, "fibra": 1.6, "sodio": 0.7},
        {"nome": "Figo, cru", "calorias": 41.4, "proteina": 1.0, "gordura_total": 0.2, "carboidratos": 10.2, "fibra": 1.8, "sodio": 0},
        {"nome": "Figo, enlatado, em calda", "calorias": 184.4, "proteina": 0.6, "gordura_total": 0.1, "carboidratos": 50.3, "fibra": 2.0, "sodio": 6.9},
        {"nome": "Fruta-pão, crua", "calorias": 67.0, "proteina": 1.1, "gordura_total": 0.2, "carboidratos": 17.2, "fibra": 5.5, "sodio": 0.8},
        {"nome": "Goiaba, branca, com casca, crua", "calorias": 51.7, "proteina": 0.9, "gordura_total": 0.5, "carboidratos": 12.4, "fibra": 6.3, "sodio": 0},
        {"nome": "Goiaba, doce em pasta", "calorias": 269.0, "proteina": 0.6, "gordura_total": 0.0, "carboidratos": 74.1, "fibra": 3.7, "sodio": 3.7},
        {"nome": "Goiaba, doce, cascão", "calorias": 285.6, "proteina": 0.4, "gordura_total": 0.1, "carboidratos": 78.7, "fibra": 4.4, "sodio": 11.0},
        {"nome": "Goiaba, vermelha, com casca, crua", "calorias": 54.2, "proteina": 1.1, "gordura_total": 0.4, "carboidratos": 13.0, "fibra": 6.2, "sodio": 0},
        {"nome": "Graviola, crua", "calorias": 61.6, "proteina": 0.8, "gordura_total": 0.2, "carboidratos": 15.8, "fibra": 1.9, "sodio": 4.2},
        {"nome": "Graviola, polpa, congelada", "calorias": 38.3, "proteina": 0.6, "gordura_total": 0.1, "carboidratos": 9.8, "fibra": 1.2, "sodio": 3.0},
        {"nome": "Jabuticaba, crua", "calorias": 58.1, "proteina": 0.6, "gordura_total": 0.1, "carboidratos": 15.3, "fibra": 2.3, "sodio": 0},
        {"nome": "Jaca, crua", "calorias": 87.9, "proteina": 1.4, "gordura_total": 0.3, "carboidratos": 22.5, "fibra": 2.4, "sodio": 1.8},
        {"nome": "Jambo, cru", "calorias": 26.9, "proteina": 0.9, "gordura_total": 0.1, "carboidratos": 6.5, "fibra": 5.1, "sodio": 21.7},
        {"nome": "Jamelão, cru", "calorias": 41.0, "proteina": 0.5, "gordura_total": 0.1, "carboidratos": 10.6, "fibra": 1.8, "sodio": 1.4},
        {"nome": "Kiwi, cru", "calorias": 51.1, "proteina": 1.3, "gordura_total": 0.6, "carboidratos": 11.5, "fibra": 2.7, "sodio": 0},
        {"nome": "Laranja, baía, crua", "calorias": 45.4, "proteina": 1.0, "gordura_total": 0.1, "carboidratos": 11.5, "fibra": 1.1, "sodio": 0},
        {"nome": "Laranja, baía, suco", "calorias": 36.6, "proteina": 0.7, "gordura_total": 0, "carboidratos": 8.7, "fibra": 0, "sodio": 0},
        {"nome": "Laranja, da terra, crua", "calorias": 51.5, "proteina": 1.1, "gordura_total": 0.2, "carboidratos": 12.9, "fibra": 4.0, "sodio": 0.8},
        {"nome": "Laranja, da terra, suco", "calorias": 41.0, "proteina": 0.7, "gordura_total": 0.1, "carboidratos": 9.6, "fibra": 1.0, "sodio": 0},
        {"nome": "Laranja, lima, crua", "calorias": 45.7, "proteina": 1.1, "gordura_total": 0.1, "carboidratos": 11.5, "fibra": 1.8, "sodio": 1.1},
        {"nome": "Laranja, lima, suco", "calorias": 39.3, "proteina": 0.7, "gordura_total": 0.1, "carboidratos": 9.2, "fibra": 0.4, "sodio": 0},
        {"nome": "Laranja, pêra, crua", "calorias": 36.8, "proteina": 1.0, "gordura_total": 0.1, "carboidratos": 8.9, "fibra": 0.8, "sodio": 0},
        {"nome": "Laranja, pêra, suco", "calorias": 32.7, "proteina": 0.7, "gordura_total": 0.1, "carboidratos": 7.6, "fibra": 0, "sodio": 0},
        {"nome": "Laranja, valência, crua", "calorias": 46.1, "proteina": 0.8, "gordura_total": 0.2, "carboidratos": 11.7, "fibra": 1.7, "sodio": 0.6},
        {"nome": "Laranja, valência, suco", "calorias": 36.2, "proteina": 0.5, "gordura_total": 0.1, "carboidratos": 8.6, "fibra": 0.4, "sodio": 0},
        {"nome": "Limão, cravo, suco", "calorias": 14.1, "proteina": 0.3, "gordura_total": 0, "carboidratos": 5.2, "fibra": 0, "sodio": 0},
        {"nome": "Limão, galego, suco", "calorias": 22.2, "proteina": 0.6, "gordura_total": 0.1, "carboidratos": 7.3, "fibra": 0, "sodio": 0},
        {"nome": "Limão, tahiti, cru", "calorias": 31.8, "proteina": 0.9, "gordura_total": 0.1, "carboidratos": 11.1, "fibra": 1.2, "sodio": 1.2},
        {"nome": "Maçã, Argentina, com casca, crua", "calorias": 62.5, "proteina": 0.2, "gordura_total": 0.2, "carboidratos": 16.6, "fibra": 2.0, "sodio": 1.3},
        {"nome": "Maçã, Fuji, com casca, crua", "calorias": 55.5, "proteina": 0.3, "gordura_total": 0, "carboidratos": 15.2, "fibra": 1.3, "sodio": 0},
        {"nome": "Macaúba, crua", "calorias": 404.3, "proteina": 2.1, "gordura_total": 40.7, "carboidratos": 13.9, "fibra": 13.4, "sodio": 0.7},
        {"nome": "Mamão, doce em calda, drenado", "calorias": 195.6, "proteina": 0.2, "gordura_total": 0.1, "carboidratos": 54.0, "fibra": 1.3, "sodio": 2.9},
        {"nome": "Mamão, Formosa, cru", "calorias": 45.3, "proteina": 0.8, "gordura_total": 0.1, "carboidratos": 11.6, "fibra": 1.8, "sodio": 3.3},
        {"nome": "Mamão, Papaia, cru", "calorias": 40.2, "proteina": 0.5, "gordura_total": 0.1, "carboidratos": 10.4, "fibra": 1.0, "sodio": 1.6},
        {"nome": "Mamão verde, doce em calda, drenado", "calorias": 209.4, "proteina": 0.3, "gordura_total": 0.1, "carboidratos": 57.6, "fibra": 1.2, "sodio": 4.7},
        {"nome": "Manga, Haden, crua", "calorias": 63.5, "proteina": 0.4, "gordura_total": 0.3, "carboidratos": 16.7, "fibra": 1.6, "sodio": 0.6},
        {"nome": "Manga, Palmer, crua", "calorias": 72.5, "proteina": 0.4, "gordura_total": 0.2, "carboidratos": 19.4, "fibra": 1.6, "sodio": 1.9},
        {"nome": "Manga, polpa, congelada", "calorias": 48.3, "proteina": 0.4, "gordura_total": 0.2, "carboidratos": 12.5, "fibra": 1.1, "sodio": 6.7},
        {"nome": "Manga, Tommy Atkins, crua", "calorias": 50.7, "proteina": 0.9, "gordura_total": 0.2, "carboidratos": 12.8, "fibra": 2.1, "sodio": 0},
        {"nome": "Maracujá, cru", "calorias": 68.4, "proteina": 2.0, "gordura_total": 2.1, "carboidratos": 12.3, "fibra": 1.1, "sodio": 1.6},
        {"nome": "Maracujá, polpa, congelada", "calorias": 38.8, "proteina": 0.8, "gordura_total": 0.2, "carboidratos": 9.6, "fibra": 0.5, "sodio": 8.1},
        {"nome": "Maracujá, suco concentrado, envasado", "calorias": 42.0, "proteina": 0.8, "gordura_total": 0.2, "carboidratos": 9.6, "fibra": 0.4, "sodio": 21.7},
        {"nome": "Melancia, crua", "calorias": 32.6, "proteina": 0.9, "gordura_total": 0, "carboidratos": 8.1, "fibra": 0.1, "sodio": 0},
        {"nome": "Melão, cru", "calorias": 29.4, "proteina": 0.7, "gordura_total": 0, "carboidratos": 7.5, "fibra": 0.2, "sodio": 11.2},
        {"nome": "Mexerica, Murcote, crua", "calorias": 57.6, "proteina": 0.9, "gordura_total": 0.1, "carboidratos": 14.9, "fibra": 3.1, "sodio": 1.2},
        {"nome": "Mexerica, Rio, crua", "calorias": 36.9, "proteina": 0.7, "gordura_total": 0.1, "carboidratos": 9.3, "fibra": 2.7, "sodio": 1.8},
        {"nome": "Morango, cru", "calorias": 30.1, "proteina": 0.9, "gordura_total": 0.3, "carboidratos": 6.8, "fibra": 1.7, "sodio": 0},
        {"nome": "Nêspera, crua", "calorias": 42.5, "proteina": 0.3, "gordura_total": 0, "carboidratos": 11.5, "fibra": 3.0, "sodio": 0},
        {"nome": "Pequi, cru", "calorias": 205.0, "proteina": 2.3, "gordura_total": 18.0, "carboidratos": 13.0, "fibra": 19.0, "sodio": 0},
        {"nome": "Pêra, Park, crua", "calorias": 60.6, "proteina": 0.2, "gordura_total": 0.2, "carboidratos": 16.1, "fibra": 3.0, "sodio": 1.0},
        {"nome": "Pêra, Williams, crua", "calorias": 53.3, "proteina": 0.6, "gordura_total": 0.1, "carboidratos": 14.0, "fibra": 3.0, "sodio": 0},
        {"nome": "Pêssego, Aurora, cru", "calorias": 36.3, "proteina": 0.8, "gordura_total": 0, "carboidratos": 9.3, "fibra": 1.4, "sodio": 0},
        {"nome": "Pêssego, enlatado, em calda", "calorias": 63.1, "proteina": 0.7, "gordura_total": 0, "carboidratos": 16.9, "fibra": 1.0, "sodio": 3.2},
        {"nome": "Pinha, crua", "calorias": 88.5, "proteina": 1.5, "gordura_total": 0.3, "carboidratos": 22.4, "fibra": 3.4, "sodio": 1.3},
        {"nome": "Pitanga, crua", "calorias": 41.4, "proteina": 0.9, "gordura_total": 0.2, "carboidratos": 10.2, "fibra": 3.2, "sodio": 1.7},
        {"nome": "Pitanga, polpa, congelada", "calorias": 19.1, "proteina": 0.3, "gordura_total": 0.1, "carboidratos": 4.8, "fibra": 0.7, "sodio": 5.0},
        {"nome": "Romã, crua", "calorias": 55.7, "proteina": 0.4, "gordura_total": 0, "carboidratos": 15.1, "fibra": 0.4, "sodio": 0.6},
        {"nome": "Tamarindo, cru", "calorias": 275.7, "proteina": 3.2, "gordura_total": 0.5, "carboidratos": 72.5, "fibra": 6.4, "sodio": 0.4},
        {"nome": "Tangerina, Poncã, crua", "calorias": 37.8, "proteina": 0.8, "gordura_total": 0.1, "carboidratos": 9.6, "fibra": 0.9, "sodio": 0},
        {"nome": "Tangerina, Poncã, suco", "calorias": 36.1, "proteina": 0.5, "gordura_total": 0, "carboidratos": 8.8, "fibra": 0, "sodio": 0},
        {"nome": "Tucumã, cru", "calorias": 262.0, "proteina": 2.1, "gordura_total": 19.1, "carboidratos": 26.5, "fibra": 12.7, "sodio": 3.9},
        {"nome": "Umbu, cru", "calorias": 37.0, "proteina": 0.8, "gordura_total": 0, "carboidratos": 9.4, "fibra": 2.0, "sodio": 0},
        {"nome": "Umbu, polpa, congelada", "calorias": 33.9, "proteina": 0.5, "gordura_total": 0.1, "carboidratos": 8.8, "fibra": 1.3, "sodio": 5.8},
        {"nome": "Uva, Itália, crua", "calorias": 52.9, "proteina": 0.7, "gordura_total": 0.2, "carboidratos": 13.6, "fibra": 0.9, "sodio": 0},
        {"nome": "Uva, Rubi, crua", "calorias": 49.1, "proteina": 0.6, "gordura_total": 0.2, "carboidratos": 12.7, "fibra": 0.9, "sodio": 7.9},
        {"nome": "Manteiga, com sal", "calorias": 726.0, "proteina": 0.4, "gordura_total": 82.4, "carboidratos": 0.1, "fibra": 0, "sodio": 578.7},
        {"nome": "Manteiga, sem sal", "calorias": 757.5, "proteina": 0.4, "gordura_total": 86.0, "carboidratos": 0.0, "fibra": 0, "sodio": 3.8},
        {"nome": "Abadejo, filé, congelado, assado", "calorias": 111.6, "proteina": 23.5, "gordura_total": 1.2, "carboidratos": 0.0, "fibra": 0, "sodio": 334.4},
        {"nome": "Abadejo, filé, congelado,cozido", "calorias": 91.1, "proteina": 19.3, "gordura_total": 0.9, "carboidratos": 0.0, "fibra": 0, "sodio": 189.3},
        {"nome": "Abadejo, filé, congelado, cru", "calorias": 59.1, "proteina": 13.1, "gordura_total": 0.4, "carboidratos": 0.0, "fibra": 0, "sodio": 78.5},
        {"nome": "Abadejo, filé, congelado, grelhado", "calorias": 129.6, "proteina": 27.6, "gordura_total": 1.3, "carboidratos": 0.0, "fibra": 0, "sodio": 305.1},
        {"nome": "Atum, conserva em óleo", "calorias": 165.9, "proteina": 26.2, "gordura_total": 6.0, "carboidratos": 0.0, "fibra": 0, "sodio": 362.1},
        {"nome": "Atum, fresco, cru", "calorias": 117.5, "proteina": 25.7, "gordura_total": 0.9, "carboidratos": 0.0, "fibra": 0, "sodio": 30.3},
        {"nome": "Bacalhau, salgado, cru", "calorias": 135.9, "proteina": 29.0, "gordura_total": 1.3, "carboidratos": 0.0, "fibra": 0, "sodio": 13585.1},
        {"nome": "Bacalhau, salgado, refogado", "calorias": 139.7, "proteina": 24.0, "gordura_total": 3.6, "carboidratos": 1.2, "fibra": 0, "sodio": 1256.3},
        {"nome": "Cação, posta, com farinha de trigo, frita", "calorias": 208.3, "proteina": 25.0, "gordura_total": 10.0, "carboidratos": 3.1, "fibra": 0.5, "sodio": 160.0},
        {"nome": "Cação, posta, cozida", "calorias": 116.0, "proteina": 25.6, "gordura_total": 0.7, "carboidratos": 0.0, "fibra": 0, "sodio": 114.9},
        {"nome": "Cação, posta, crua", "calorias": 83.3, "proteina": 17.9, "gordura_total": 0.8, "carboidratos": 0.0, "fibra": 0, "sodio": 176.0},
        {"nome": "Camarão, Rio Grande, grande, cozido", "calorias": 90.0, "proteina": 19.0, "gordura_total": 1.0, "carboidratos": 0.0, "fibra": 0, "sodio": 366.6},
        {"nome": "Camarão, Rio Grande, grande, cru", "calorias": 47.2, "proteina": 10.0, "gordura_total": 0.5, "carboidratos": 0.0, "fibra": 0, "sodio": 201.1},
        {"nome": "Camarão, Sete Barbas, sem cabeça, com casca, frito", "calorias": 231.2, "proteina": 18.4, "gordura_total": 15.6, "carboidratos": 2.9, "fibra": 0, "sodio": 99.1},
        {"nome": "Caranguejo, cozido", "calorias": 82.7, "proteina": 18.5, "gordura_total": 0.4, "carboidratos": 0.0, "fibra": 0, "sodio": 360.1},
        {"nome": "Corimba, cru", "calorias": 128.2, "proteina": 17.4, "gordura_total": 6.0, "carboidratos": -0.0, "fibra": 0, "sodio": 47.0},
        {"nome": "Corimbatá, assado", "calorias": 261.5, "proteina": 19.9, "gordura_total": 19.6, "carboidratos": 0.0, "fibra": 0, "sodio": 40.4},
        {"nome": "Corimbatá, cozido", "calorias": 238.7, "proteina": 20.1, "gordura_total": 16.9, "carboidratos": 0.0, "fibra": 0, "sodio": 37.2},
        {"nome": "Corvina de água doce, crua", "calorias": 101.0, "proteina": 18.9, "gordura_total": 2.2, "carboidratos": 0.0, "fibra": 0, "sodio": 45.1},
        {"nome": "Corvina do mar, crua", "calorias": 94.0, "proteina": 18.6, "gordura_total": 1.6, "carboidratos": 0.0, "fibra": 0, "sodio": 68.0},
        {"nome": "Corvina grande, assada", "calorias": 146.5, "proteina": 26.8, "gordura_total": 3.6, "carboidratos": 0.0, "fibra": 0, "sodio": 85.4},
        {"nome": "Corvina grande, cozida", "calorias": 100.1, "proteina": 23.4, "gordura_total": 2.6, "carboidratos": 0.0, "fibra": 0, "sodio": 68.4},
        {"nome": "Dourada de água doce, fresca", "calorias": 131.2, "proteina": 18.8, "gordura_total": 5.6, "carboidratos": 0.0, "fibra": 0, "sodio": 40.3},
        {"nome": "Lambari, congelado, cru", "calorias": 130.8, "proteina": 16.8, "gordura_total": 6.5, "carboidratos": 0.0, "fibra": 0, "sodio": 47.9},
        {"nome": "Lambari, congelado, frito", "calorias": 326.9, "proteina": 28.4, "gordura_total": 22.8, "carboidratos": 0.0, "fibra": 0, "sodio": 64.6},
        {"nome": "Lambari, fresco, cru", "calorias": 151.6, "proteina": 15.7, "gordura_total": 9.4, "carboidratos": 0.0, "fibra": 0, "sodio": 41.1},
        {"nome": "Manjuba, com farinha de trigo, frita", "calorias": 343.6, "proteina": 23.4, "gordura_total": 22.6, "carboidratos": 10.2, "fibra": 0.4, "sodio": 36.5},
        {"nome": "Manjuba, frita", "calorias": 349.3, "proteina": 30.1, "gordura_total": 24.5, "carboidratos": 0.0, "fibra": 0, "sodio": 40.6},
        {"nome": "Merluza, filé, assado", "calorias": 121.9, "proteina": 26.6, "gordura_total": 0.9, "carboidratos": 0.0, "fibra": 0, "sodio": 119.9},
        {"nome": "Merluza, filé, cru", "calorias": 89.1, "proteina": 16.6, "gordura_total": 2.0, "carboidratos": 0.0, "fibra": 0, "sodio": 79.5},
        {"nome": "Merluza, filé, frito", "calorias": 191.6, "proteina": 26.9, "gordura_total": 8.5, "carboidratos": 0.0, "fibra": 0, "sodio": 90.0},
        {"nome": "Pescada, branca, crua", "calorias": 110.9, "proteina": 16.3, "gordura_total": 4.6, "carboidratos": 0.0, "fibra": 0, "sodio": 76.2},
        {"nome": "Pescada, branca, frita", "calorias": 223.0, "proteina": 27.4, "gordura_total": 11.8, "carboidratos": 0.0, "fibra": 0, "sodio": 107.2},
        {"nome": "Pescada, filé, com farinha de trigo, frito", "calorias": 283.4, "proteina": 21.4, "gordura_total": 19.1, "carboidratos": 5.0, "fibra": 0, "sodio": 90.5},
        {"nome": "Pescada, filé, cru", "calorias": 107.2, "proteina": 16.6, "gordura_total": 4.0, "carboidratos": 0.0, "fibra": 0, "sodio": 77.5},
        {"nome": "Pescada, filé, frito", "calorias": 154.3, "proteina": 28.6, "gordura_total": 3.6, "carboidratos": 0.0, "fibra": 0, "sodio": 114.9},
        {"nome": "Pescada, filé, molho escabeche", "calorias": 142.0, "proteina": 11.8, "gordura_total": 8.0, "carboidratos": 5.0, "fibra": 0.8, "sodio": 51.3},
        {"nome": "Pescadinha, crua", "calorias": 76.4, "proteina": 15.5, "gordura_total": 1.1, "carboidratos": 0.0, "fibra": 0, "sodio": 120.3},
        {"nome": "Pintado, assado", "calorias": 191.6, "proteina": 36.5, "gordura_total": 4.0, "carboidratos": 0.0, "fibra": 0, "sodio": 81.0},
        {"nome": "Pintado, cru", "calorias": 91.1, "proteina": 18.6, "gordura_total": 1.3, "carboidratos": 0.0, "fibra": 0, "sodio": 43.3},
        {"nome": "Pintado, grelhado", "calorias": 152.2, "proteina": 30.8, "gordura_total": 2.3, "carboidratos": 0.0, "fibra": 0, "sodio": 53.1},
        {"nome": "Porquinho, cru", "calorias": 93.0, "proteina": 20.5, "gordura_total": 0.6, "carboidratos": 0.0, "fibra": 0, "sodio": 66.7},
        {"nome": "Salmão, filé, com pele, fresco,  grelhado", "calorias": 228.7, "proteina": 23.9, "gordura_total": 14.0, "carboidratos": 0.0, "fibra": 0, "sodio": 85.1},
        {"nome": "Salmão, sem pele, fresco, cru", "calorias": 169.8, "proteina": 19.3, "gordura_total": 9.7, "carboidratos": 0.0, "fibra": 0, "sodio": 64.2},
        {"nome": "Salmão, sem pele, fresco, grelhado", "calorias": 242.7, "proteina": 26.1, "gordura_total": 14.5, "carboidratos": 0.0, "fibra": 0, "sodio": 95.8},
        {"nome": "Sardinha, assada", "calorias": 164.4, "proteina": 32.2, "gordura_total": 3.0, "carboidratos": 0.0, "fibra": 0, "sodio": 74.5},
        {"nome": "Sardinha, conserva em óleo", "calorias": 285.0, "proteina": 15.9, "gordura_total": 24.0, "carboidratos": 0.0, "fibra": 0, "sodio": 665.8},
        {"nome": "Sardinha, frita", "calorias": 257.0, "proteina": 33.4, "gordura_total": 12.7, "carboidratos": 0.0, "fibra": 0, "sodio": 60.1},
        {"nome": "Sardinha, inteira, crua", "calorias": 113.9, "proteina": 21.1, "gordura_total": 2.6, "carboidratos": 0.0, "fibra": 0, "sodio": 60.4},
        {"nome": "Tucunaré, filé, congelado, cru", "calorias": 87.7, "proteina": 18.0, "gordura_total": 1.2, "carboidratos": -0.0, "fibra": 0, "sodio": 56.6},
        {"nome": "Apresuntado", "calorias": 128.9, "proteina": 13.4, "gordura_total": 6.7, "carboidratos": 2.9, "fibra": 0, "sodio": 942.9},
        {"nome": "Caldo de carne, tablete", "calorias": 240.6, "proteina": 7.8, "gordura_total": 16.6, "carboidratos": 15.1, "fibra": 0.6, "sodio": 22179.7},
        {"nome": "Caldo de galinha, tablete", "calorias": 251.4, "proteina": 6.3, "gordura_total": 20.4, "carboidratos": 10.6, "fibra": 11.8, "sodio": 22299.9},
        {"nome": "Carne, bovina, acém, moído, cozido", "calorias": 212.4, "proteina": 26.7, "gordura_total": 10.9, "carboidratos": 0.0, "fibra": 0, "sodio": 52.4},
        {"nome": "Carne, bovina, acém, moído, cru", "calorias": 136.6, "proteina": 19.4, "gordura_total": 5.9, "carboidratos": 0.0, "fibra": 0, "sodio": 48.6},
        {"nome": "Carne, bovina, acém, sem gordura, cozido", "calorias": 214.6, "proteina": 27.3, "gordura_total": 10.9, "carboidratos": 0.0, "fibra": 0, "sodio": 56.2},
        {"nome": "Carne, bovina, acém, sem gordura, cru", "calorias": 144.0, "proteina": 20.8, "gordura_total": 6.1, "carboidratos": 0.0, "fibra": 0, "sodio": 49.8},
        {"nome": "Carne, bovina, almôndegas, cruas", "calorias": 189.3, "proteina": 12.3, "gordura_total": 11.2, "carboidratos": 9.8, "fibra": 0, "sodio": 621.3},
        {"nome": "Carne, bovina, almôndegas, fritas", "calorias": 271.8, "proteina": 18.2, "gordura_total": 15.8, "carboidratos": 14.3, "fibra": 0, "sodio": 1030.3},
        {"nome": "Carne, bovina, bucho, cozido", "calorias": 133.0, "proteina": 21.6, "gordura_total": 4.5, "carboidratos": 0.0, "fibra": 0, "sodio": 38.2},
        {"nome": "Carne, bovina, bucho, cru", "calorias": 137.3, "proteina": 20.5, "gordura_total": 5.5, "carboidratos": 0.0, "fibra": 0, "sodio": 45.0},
        {"nome": "Carne, bovina, capa de contra-filé, com gordura, crua", "calorias": 216.9, "proteina": 19.2, "gordura_total": 15.0, "carboidratos": 0.0, "fibra": 0, "sodio": 57.5},
        {"nome": "Carne, bovina, capa de contra-filé, com gordura, grelhada", "calorias": 311.7, "proteina": 30.7, "gordura_total": 20.0, "carboidratos": 0.0, "fibra": 0, "sodio": 80.5},
        {"nome": "Carne, bovina, capa de contra-filé, sem gordura, crua", "calorias": 131.1, "proteina": 21.5, "gordura_total": 4.3, "carboidratos": 0.0, "fibra": 0, "sodio": 79.2},
        {"nome": "Carne, bovina, capa de contra-filé, sem gordura, grelhada", "calorias": 239.4, "proteina": 35.1, "gordura_total": 9.9, "carboidratos": -0.0, "fibra": 0, "sodio": 82.8},
        {"nome": "Carne, bovina, charque, cozido", "calorias": 262.8, "proteina": 36.4, "gordura_total": 11.9, "carboidratos": 0.0, "fibra": 0, "sodio": 1442.7},
        {"nome": "Carne, bovina, charque, cru", "calorias": 248.9, "proteina": 22.7, "gordura_total": 16.8, "carboidratos": 0.0, "fibra": 0, "sodio": 5875.0},
        {"nome": "Carne, bovina, contra-filé, à milanesa", "calorias": 351.6, "proteina": 20.6, "gordura_total": 24.0, "carboidratos": 12.2, "fibra": 0.4, "sodio": 77.1},
        {"nome": "Carne, bovina, contra-filé de costela, cru", "calorias": 202.4, "proteina": 19.8, "gordura_total": 13.1, "carboidratos": 0.0, "fibra": 0, "sodio": 38.5},
        {"nome": "Carne, bovina, contra-filé de costela, grelhado", "calorias": 274.9, "proteina": 29.9, "gordura_total": 16.3, "carboidratos": 0.0, "fibra": 0, "sodio": 50.9},
        {"nome": "Carne, bovina, contra-filé, com gordura, cru", "calorias": 205.9, "proteina": 21.1, "gordura_total": 12.8, "carboidratos": 0.0, "fibra": 0, "sodio": 44.1},
        {"nome": "Carne, bovina, contra-filé, com gordura, grelhado", "calorias": 278.1, "proteina": 32.4, "gordura_total": 15.5, "carboidratos": 0.0, "fibra": 0, "sodio": 57.1},
        {"nome": "Carne, bovina, contra-filé, sem gordura, cru", "calorias": 156.6, "proteina": 24.0, "gordura_total": 6.0, "carboidratos": 0.0, "fibra": 0, "sodio": 52.9},
        {"nome": "Carne, bovina, contra-filé, sem gordura, grelhado", "calorias": 193.7, "proteina": 35.9, "gordura_total": 4.5, "carboidratos": 0.0, "fibra": 0, "sodio": 57.5},
        {"nome": "Carne, bovina, costela, assada", "calorias": 373.0, "proteina": 28.8, "gordura_total": 27.7, "carboidratos": 0.0, "fibra": 0, "sodio": 91.9},
        {"nome": "Carne, bovina, costela, crua", "calorias": 357.7, "proteina": 16.7, "gordura_total": 31.8, "carboidratos": 0.0, "fibra": 0, "sodio": 70.0},
        {"nome": "Carne, bovina, coxão duro, sem gordura, cozido", "calorias": 216.6, "proteina": 31.9, "gordura_total": 8.9, "carboidratos": 0.0, "fibra": 0, "sodio": 41.1},
        {"nome": "Carne, bovina, coxão duro, sem gordura, cru", "calorias": 148.0, "proteina": 21.5, "gordura_total": 6.2, "carboidratos": 0.0, "fibra": 0, "sodio": 48.5},
        {"nome": "Carne, bovina, coxão mole, sem gordura, cozido", "calorias": 218.7, "proteina": 32.4, "gordura_total": 8.9, "carboidratos": 0.0, "fibra": 0, "sodio": 43.5},
        {"nome": "Carne, bovina, coxão mole, sem gordura, cru", "calorias": 169.1, "proteina": 21.2, "gordura_total": 8.7, "carboidratos": 0.0, "fibra": 0, "sodio": 60.5},
        {"nome": "Carne, bovina, cupim, assado", "calorias": 330.1, "proteina": 28.6, "gordura_total": 23.0, "carboidratos": 0.0, "fibra": 0, "sodio": 71.6},
        {"nome": "Carne, bovina, cupim, cru", "calorias": 221.4, "proteina": 19.5, "gordura_total": 15.3, "carboidratos": 0.0, "fibra": 0, "sodio": 46.9},
        {"nome": "Carne, bovina, fígado, cru", "calorias": 141.0, "proteina": 20.7, "gordura_total": 5.4, "carboidratos": 1.1, "fibra": 0, "sodio": 75.9},
        {"nome": "Carne, bovina, fígado, grelhado", "calorias": 225.0, "proteina": 29.9, "gordura_total": 9.0, "carboidratos": 4.2, "fibra": 0, "sodio": 82.2},
        {"nome": "Carne, bovina, filé mingnon, sem gordura, cru", "calorias": 142.9, "proteina": 21.6, "gordura_total": 5.6, "carboidratos": 0.0, "fibra": 0, "sodio": 48.9},
        {"nome": "Carne, bovina, filé mingnon, sem gordura, grelhado", "calorias": 219.7, "proteina": 32.8, "gordura_total": 8.8, "carboidratos": 0.0, "fibra": 0, "sodio": 57.9},
        {"nome": "Carne, bovina, flanco, sem gordura, cozido", "calorias": 195.6, "proteina": 29.4, "gordura_total": 7.8, "carboidratos": 0.0, "fibra": 0, "sodio": 41.7},
        {"nome": "Carne, bovina, flanco, sem gordura, cru", "calorias": 141.5, "proteina": 20.0, "gordura_total": 6.2, "carboidratos": 0.0, "fibra": 0, "sodio": 54.2},
        {"nome": "Carne, bovina, fraldinha, com gordura, cozida", "calorias": 338.4, "proteina": 24.2, "gordura_total": 26.0, "carboidratos": 0.0, "fibra": 0, "sodio": 38.8},
        {"nome": "Carne, bovina, fraldinha, com gordura, crua", "calorias": 220.7, "proteina": 17.6, "gordura_total": 16.1, "carboidratos": 0.0, "fibra": 0, "sodio": 51.2},
        {"nome": "Carne, bovina, lagarto, cozido", "calorias": 222.5, "proteina": 32.9, "gordura_total": 9.1, "carboidratos": 0.0, "fibra": 0, "sodio": 47.5},
        {"nome": "Carne, bovina, lagarto, cru", "calorias": 134.9, "proteina": 20.5, "gordura_total": 5.2, "carboidratos": 0.0, "fibra": 0, "sodio": 53.6},
        {"nome": "Carne, bovina, língua, cozida", "calorias": 314.9, "proteina": 21.4, "gordura_total": 24.8, "carboidratos": 0.0, "fibra": 0, "sodio": 59.1},
        {"nome": "Carne, bovina, língua, crua", "calorias": 215.2, "proteina": 17.1, "gordura_total": 15.8, "carboidratos": 0.0, "fibra": 0, "sodio": 73.0},
        {"nome": "Carne, bovina, maminha, crua", "calorias": 152.8, "proteina": 20.9, "gordura_total": 7.0, "carboidratos": 0.0, "fibra": 0, "sodio": 37.4},
        {"nome": "Carne, bovina, maminha, grelhada", "calorias": 153.1, "proteina": 30.7, "gordura_total": 2.4, "carboidratos": 0.0, "fibra": 0, "sodio": 58.1},
        {"nome": "Carne, bovina, miolo de alcatra, sem gordura, cru", "calorias": 162.9, "proteina": 21.6, "gordura_total": 7.8, "carboidratos": 0.0, "fibra": 0, "sodio": 43.1},
        {"nome": "Carne, bovina, miolo de alcatra, sem gordura, grelhado", "calorias": 241.4, "proteina": 31.9, "gordura_total": 11.6, "carboidratos": 0.0, "fibra": 0, "sodio": 51.6},
        {"nome": "Carne, bovina, músculo, sem gordura, cozido", "calorias": 193.8, "proteina": 31.2, "gordura_total": 6.7, "carboidratos": 0.0, "fibra": 0, "sodio": 61.8},
        {"nome": "Carne, bovina, músculo, sem gordura, cru", "calorias": 141.6, "proteina": 21.6, "gordura_total": 5.5, "carboidratos": 0.0, "fibra": 0, "sodio": 66.1},
        {"nome": "Carne, bovina, paleta, com gordura, crua", "calorias": 158.7, "proteina": 21.4, "gordura_total": 7.5, "carboidratos": 0.0, "fibra": 0, "sodio": 64.9},
        {"nome": "Carne, bovina, paleta, sem gordura, cozida", "calorias": 193.7, "proteina": 29.7, "gordura_total": 7.4, "carboidratos": 0.0, "fibra": 0, "sodio": 57.6},
        {"nome": "Carne, bovina, paleta, sem gordura, crua", "calorias": 140.9, "proteina": 21.0, "gordura_total": 5.7, "carboidratos": 0.0, "fibra": 0, "sodio": 65.9},
        {"nome": "Carne, bovina, patinho, sem gordura, cru", "calorias": 133.5, "proteina": 21.7, "gordura_total": 4.5, "carboidratos": 0.0, "fibra": 0, "sodio": 49.1},
        {"nome": "Carne, bovina, patinho, sem gordura, grelhado", "calorias": 219.3, "proteina": 35.9, "gordura_total": 7.3, "carboidratos": 0.0, "fibra": 0, "sodio": 60.3},
        {"nome": "Carne, bovina, peito, sem gordura, cozido", "calorias": 338.5, "proteina": 22.2, "gordura_total": 27.0, "carboidratos": 0.0, "fibra": 0, "sodio": 55.7},
        {"nome": "Carne, bovina, peito, sem gordura, cru", "calorias": 259.3, "proteina": 17.6, "gordura_total": 20.4, "carboidratos": 0.0, "fibra": 0, "sodio": 63.8},
        {"nome": "Carne, bovina, picanha, com gordura, crua", "calorias": 212.9, "proteina": 18.8, "gordura_total": 14.7, "carboidratos": 0.0, "fibra": 0, "sodio": 37.6},
        {"nome": "Carne, bovina, picanha, com gordura, grelhada", "calorias": 288.8, "proteina": 26.4, "gordura_total": 19.5, "carboidratos": 0.0, "fibra": 0, "sodio": 60.0},
        {"nome": "Carne, bovina, picanha, sem gordura, crua", "calorias": 133.5, "proteina": 21.2, "gordura_total": 4.7, "carboidratos": 0.0, "fibra": 0, "sodio": 61.1},
        {"nome": "Carne, bovina, picanha, sem gordura, grelhada", "calorias": 238.5, "proteina": 31.9, "gordura_total": 11.3, "carboidratos": 0.0, "fibra": 0, "sodio": 60.7},
        {"nome": "Carne, bovina, seca, cozida", "calorias": 312.8, "proteina": 26.9, "gordura_total": 21.9, "carboidratos": 0.0, "fibra": 0, "sodio": 1943.2},
        {"nome": "Carne, bovina, seca, crua", "calorias": 312.7, "proteina": 19.7, "gordura_total": 25.4, "carboidratos": 0.0, "fibra": 0, "sodio": 4439.6},
        {"nome": "Coxinha de frango, frita", "calorias": 283.0, "proteina": 9.6, "gordura_total": 11.8, "carboidratos": 34.5, "fibra": 5.0, "sodio": 532.1},
        {"nome": "Croquete, de carne, cru", "calorias": 245.8, "proteina": 12.0, "gordura_total": 15.6, "carboidratos": 13.9, "fibra": 0, "sodio": 710.6},
        {"nome": "Croquete, de carne, frito", "calorias": 346.7, "proteina": 16.9, "gordura_total": 22.7, "carboidratos": 18.1, "fibra": 0, "sodio": 916.4},
        {"nome": "Empada de frango, pré-cozida, assada", "calorias": 358.2, "proteina": 6.9, "gordura_total": 15.6, "carboidratos": 47.5, "fibra": 2.2, "sodio": 524.9},
        {"nome": "Empada, de frango, pré-cozida", "calorias": 377.5, "proteina": 7.3, "gordura_total": 22.9, "carboidratos": 35.5, "fibra": 2.2, "sodio": 770.7},
        {"nome": "Frango, asa, com pele, crua", "calorias": 213.2, "proteina": 18.1, "gordura_total": 15.1, "carboidratos": 0.0, "fibra": 0, "sodio": 96.3},
        {"nome": "Frango, caipira, inteiro, com pele, cozido", "calorias": 242.9, "proteina": 23.9, "gordura_total": 15.6, "carboidratos": 0.0, "fibra": 0, "sodio": 56.1},
        {"nome": "Frango, caipira, inteiro, sem pele, cozido", "calorias": 195.8, "proteina": 29.6, "gordura_total": 7.7, "carboidratos": 0.0, "fibra": 0, "sodio": 53.2},
        {"nome": "Frango, coração, cru", "calorias": 221.5, "proteina": 12.6, "gordura_total": 18.6, "carboidratos": 0.0, "fibra": 0, "sodio": 95.1},
        {"nome": "Frango, coração, grelhado", "calorias": 207.3, "proteina": 22.4, "gordura_total": 12.1, "carboidratos": 0.6, "fibra": 0, "sodio": 128.2},
        {"nome": "Frango, coxa, com pele, assada", "calorias": 215.1, "proteina": 28.5, "gordura_total": 10.4, "carboidratos": 0.1, "fibra": 0, "sodio": 94.8},
        {"nome": "Frango, coxa, com pele, crua", "calorias": 161.5, "proteina": 17.1, "gordura_total": 9.8, "carboidratos": 0.0, "fibra": 0, "sodio": 95.0},
        {"nome": "Frango, coxa, sem pele, cozida", "calorias": 167.4, "proteina": 26.9, "gordura_total": 5.8, "carboidratos": 0.0, "fibra": 0, "sodio": 64.3},
        {"nome": "Frango, coxa, sem pele, crua", "calorias": 119.9, "proteina": 17.8, "gordura_total": 4.9, "carboidratos": 0.0, "fibra": 0, "sodio": 98.4},
        {"nome": "Frango, fígado, cru", "calorias": 106.5, "proteina": 17.6, "gordura_total": 3.5, "carboidratos": -0.0, "fibra": 0, "sodio": 82.4},
        {"nome": "Frango, filé, à milanesa", "calorias": 220.9, "proteina": 28.5, "gordura_total": 7.8, "carboidratos": 7.5, "fibra": 1.1, "sodio": 122.3},
        {"nome": "Frango, inteiro, com pele, cru", "calorias": 226.3, "proteina": 16.4, "gordura_total": 17.3, "carboidratos": 0.0, "fibra": 0, "sodio": 62.9},
        {"nome": "Frango, inteiro, sem pele, assado", "calorias": 187.3, "proteina": 28.0, "gordura_total": 7.5, "carboidratos": 0.0, "fibra": 0, "sodio": 70.3},
        {"nome": "Frango, inteiro, sem pele, cozido", "calorias": 170.4, "proteina": 25.0, "gordura_total": 7.1, "carboidratos": 0.0, "fibra": 0, "sodio": 50.9},
        {"nome": "Frango, inteiro, sem pele, cru", "calorias": 129.1, "proteina": 20.6, "gordura_total": 4.6, "carboidratos": 0.0, "fibra": 0, "sodio": 73.0},
        {"nome": "Frango, peito, com pele, assado", "calorias": 211.7, "proteina": 33.4, "gordura_total": 7.6, "carboidratos": 0.0, "fibra": 0, "sodio": 55.7},
        {"nome": "Frango, peito, com pele, cru", "calorias": 149.5, "proteina": 20.8, "gordura_total": 6.7, "carboidratos": 0.0, "fibra": 0, "sodio": 62.3},
        {"nome": "Frango, peito, sem pele, cozido", "calorias": 162.9, "proteina": 31.5, "gordura_total": 3.2, "carboidratos": 0.0, "fibra": 0, "sodio": 36.2},
        {"nome": "Frango, peito, sem pele, cru", "calorias": 119.2, "proteina": 21.5, "gordura_total": 3.0, "carboidratos": 0.0, "fibra": 0, "sodio": 56.1},
        {"nome": "Frango, peito, sem pele, grelhado", "calorias": 159.2, "proteina": 32.0, "gordura_total": 2.5, "carboidratos": 0.0, "fibra": 0, "sodio": 50.2},
        {"nome": "Frango, sobrecoxa, com pele, assada", "calorias": 259.6, "proteina": 28.7, "gordura_total": 15.2, "carboidratos": 0.0, "fibra": 0, "sodio": 95.9},
        {"nome": "Frango, sobrecoxa, com pele, crua", "calorias": 254.5, "proteina": 15.5, "gordura_total": 20.9, "carboidratos": 0.0, "fibra": 0, "sodio": 68.3},
        {"nome": "Frango, sobrecoxa, sem pele, assada", "calorias": 232.9, "proteina": 29.2, "gordura_total": 12.0, "carboidratos": 0.0, "fibra": 0, "sodio": 106.1},
        {"nome": "Frango, sobrecoxa, sem pele, crua", "calorias": 161.8, "proteina": 17.6, "gordura_total": 9.6, "carboidratos": 0.0, "fibra": 0, "sodio": 79.7},
        {"nome": "Hambúrguer, bovino, cru", "calorias": 214.8, "proteina": 13.2, "gordura_total": 16.2, "carboidratos": 4.2, "fibra": 0, "sodio": 869.5},
        {"nome": "Hambúrguer, bovino, frito", "calorias": 258.3, "proteina": 20.0, "gordura_total": 17.0, "carboidratos": 6.3, "fibra": 0, "sodio": 1251.8},
        {"nome": "Hambúrguer, bovino, grelhado", "calorias": 209.8, "proteina": 13.2, "gordura_total": 12.4, "carboidratos": 11.3, "fibra": 0, "sodio": 1090.3},
        {"nome": "Lingüiça, frango, crua", "calorias": 218.1, "proteina": 14.2, "gordura_total": 17.4, "carboidratos": 0.0, "fibra": 0, "sodio": 1125.8},
        {"nome": "Lingüiça, frango, frita", "calorias": 245.5, "proteina": 18.3, "gordura_total": 18.5, "carboidratos": 0.0, "fibra": 0, "sodio": 1373.9},
        {"nome": "Lingüiça, frango, grelhada", "calorias": 243.7, "proteina": 18.2, "gordura_total": 18.4, "carboidratos": 0.0, "fibra": 0, "sodio": 1351.5},
        {"nome": "Lingüiça, porco, crua", "calorias": 227.2, "proteina": 16.1, "gordura_total": 17.6, "carboidratos": 0.0, "fibra": 0, "sodio": 1175.7},
        {"nome": "Lingüiça, porco, frita", "calorias": 279.5, "proteina": 20.5, "gordura_total": 21.3, "carboidratos": 0.0, "fibra": 0, "sodio": 1431.6},
        {"nome": "Lingüiça, porco, grelhada", "calorias": 296.5, "proteina": 23.2, "gordura_total": 21.9, "carboidratos": 0.0, "fibra": 0, "sodio": 1455.9},
        {"nome": "Mortadela", "calorias": 268.8, "proteina": 12.0, "gordura_total": 21.6, "carboidratos": 5.8, "fibra": 0, "sodio": 1212.2},
        {"nome": "Peru, congelado, assado", "calorias": 163.1, "proteina": 26.2, "gordura_total": 5.7, "carboidratos": 0.0, "fibra": 0, "sodio": 627.9},
        {"nome": "Peru, congelado, cru", "calorias": 93.7, "proteina": 18.1, "gordura_total": 1.8, "carboidratos": 0.0, "fibra": 0, "sodio": 710.7},
        {"nome": "Porco, bisteca, crua", "calorias": 164.1, "proteina": 21.5, "gordura_total": 8.0, "carboidratos": 0.0, "fibra": 0, "sodio": 54.3},
        {"nome": "Porco, bisteca, frita", "calorias": 311.2, "proteina": 33.7, "gordura_total": 18.5, "carboidratos": 0.0, "fibra": 0, "sodio": 63.0},
        {"nome": "Porco, bisteca, grelhada", "calorias": 280.1, "proteina": 28.9, "gordura_total": 17.4, "carboidratos": 0.0, "fibra": 0, "sodio": 51.4},
        {"nome": "Porco, costela, assada", "calorias": 402.2, "proteina": 30.2, "gordura_total": 30.3, "carboidratos": 0.0, "fibra": 0, "sodio": 62.7},
        {"nome": "Porco, costela, crua", "calorias": 255.6, "proteina": 18.0, "gordura_total": 19.8, "carboidratos": 0.0, "fibra": 0, "sodio": 88.0},
        {"nome": "Porco, lombo, assado", "calorias": 210.2, "proteina": 35.7, "gordura_total": 6.4, "carboidratos": 0.0, "fibra": 0, "sodio": 38.9},
        {"nome": "Porco, lombo, cru", "calorias": 175.6, "proteina": 22.6, "gordura_total": 8.8, "carboidratos": 0.0, "fibra": 0, "sodio": 53.1},
        {"nome": "Porco, orelha, salgada, crua", "calorias": 258.5, "proteina": 18.5, "gordura_total": 19.9, "carboidratos": 0.0, "fibra": 0, "sodio": 615.6},
        {"nome": "Porco, pernil, assado", "calorias": 262.3, "proteina": 32.1, "gordura_total": 13.9, "carboidratos": 0.0, "fibra": 0, "sodio": 62.4},
        {"nome": "Porco, pernil, cru", "calorias": 186.1, "proteina": 20.1, "gordura_total": 11.1, "carboidratos": 0.0, "fibra": 0, "sodio": 101.9},
        {"nome": "Porco, rabo, salgado, cru", "calorias": 377.4, "proteina": 15.6, "gordura_total": 34.5, "carboidratos": 0.0, "fibra": 0, "sodio": 1157.7},
        {"nome": "Presunto, com capa de gordura", "calorias": 127.8, "proteina": 14.4, "gordura_total": 6.8, "carboidratos": 1.4, "fibra": 0, "sodio": 1020.8},
        {"nome": "Presunto, sem capa de gordura", "calorias": 93.7, "proteina": 14.3, "gordura_total": 2.7, "carboidratos": 2.1, "fibra": 0, "sodio": 1039.2},
        {"nome": "Quibe, assado", "calorias": 136.2, "proteina": 14.6, "gordura_total": 2.7, "carboidratos": 12.9, "fibra": 1.9, "sodio": 39.9},
        {"nome": "Quibe, cru", "calorias": 109.5, "proteina": 12.4, "gordura_total": 1.7, "carboidratos": 10.8, "fibra": 1.6, "sodio": 38.8},
        {"nome": "Quibe, frito", "calorias": 253.8, "proteina": 14.9, "gordura_total": 15.8, "carboidratos": 12.3, "fibra": 0, "sodio": 835.8},
        {"nome": "Salame", "calorias": 397.8, "proteina": 25.8, "gordura_total": 30.6, "carboidratos": 2.9, "fibra": 0, "sodio": 1574.2},
        {"nome": "Toucinho, cru", "calorias": 592.5, "proteina": 11.5, "gordura_total": 60.3, "carboidratos": 0.0, "fibra": 0, "sodio": 49.6},
        {"nome": "Toucinho, frito", "calorias": 696.6, "proteina": 27.3, "gordura_total": 64.3, "carboidratos": 0.0, "fibra": 0, "sodio": 124.9},
        {"nome": "Bebida láctea, pêssego", "calorias": 55.2, "proteina": 2.1, "gordura_total": 1.9, "carboidratos": 7.6, "fibra": 0.3, "sodio": 46.3},
        {"nome": "Iogurte, natural", "calorias": 51.5, "proteina": 4.1, "gordura_total": 3.0, "carboidratos": 1.9, "fibra": 0, "sodio": 51.6},
        {"nome": "Iogurte, natural, desnatado", "calorias": 41.5, "proteina": 3.8, "gordura_total": 0.3, "carboidratos": 5.8, "fibra": 0, "sodio": 59.6},
        {"nome": "Iogurte, sabor morango", "calorias": 69.6, "proteina": 2.7, "gordura_total": 2.3, "carboidratos": 9.7, "fibra": 0.2, "sodio": 37.7},
        {"nome": "Iogurte, sabor pêssego", "calorias": 67.8, "proteina": 2.5, "gordura_total": 2.3, "carboidratos": 9.4, "fibra": 0.7, "sodio": 37.0},
        {"nome": "Queijo, minas, frescal", "calorias": 264.3, "proteina": 17.4, "gordura_total": 20.2, "carboidratos": 3.2, "fibra": 0, "sodio": 31.2},
        {"nome": "Queijo, minas, meia cura", "calorias": 320.7, "proteina": 21.2, "gordura_total": 24.6, "carboidratos": 3.6, "fibra": 0, "sodio": 501.2},
        {"nome": "Queijo, mozarela", "calorias": 329.9, "proteina": 22.6, "gordura_total": 25.2, "carboidratos": 3.0, "fibra": 0, "sodio": 581.4},
        {"nome": "Queijo, parmesão", "calorias": 453.0, "proteina": 35.6, "gordura_total": 33.5, "carboidratos": 1.7, "fibra": 0, "sodio": 1844.1},
        {"nome": "Queijo, pasteurizado", "calorias": 303.1, "proteina": 9.4, "gordura_total": 27.4, "carboidratos": 5.7, "fibra": 0, "sodio": 780.4},
        {"nome": "Queijo, petit suisse, morango", "calorias": 121.1, "proteina": 5.8, "gordura_total": 2.8, "carboidratos": 18.5, "fibra": 0, "sodio": 412.5},
        {"nome": "Queijo, prato", "calorias": 359.9, "proteina": 22.7, "gordura_total": 29.1, "carboidratos": 1.9, "fibra": 0, "sodio": 579.8},
        {"nome": "Queijo, requeijão, cremoso", "calorias": 256.6, "proteina": 9.6, "gordura_total": 23.4, "carboidratos": 2.4, "fibra": 0, "sodio": 557.9},
        {"nome": "Queijo, ricota", "calorias": 139.7, "proteina": 12.6, "gordura_total": 8.1, "carboidratos": 3.8, "fibra": 0, "sodio": 282.6},
        {"nome": "Bebida isotônica, sabores variados", "calorias": 25.6, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 6.4, "fibra": 0, "sodio": 44.1},
        {"nome": "Café, infusão 10%", "calorias": 9.1, "proteina": 0.7, "gordura_total": 0.1, "carboidratos": 1.5, "fibra": 0, "sodio": 1.0},
        {"nome": "Cerveja, pilsen 2", "calorias": 40.7, "proteina": 0.6, "gordura_total": 0, "carboidratos": 3.3, "fibra": 0, "sodio": 4.2},
        {"nome": "Chá, erva-doce, infusão 5%", "calorias": 1.4, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 0.4, "fibra": 0, "sodio": 0.6},
        {"nome": "Chá, mate, infusão 5%", "calorias": 2.7, "proteina": 0.0, "gordura_total": 0.1, "carboidratos": 0.6, "fibra": 0, "sodio": 0},
        {"nome": "Chá, preto, infusão 5%", "calorias": 2.2, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 0.6, "fibra": 0, "sodio": 0},
        {"nome": "Coco, água de", "calorias": 21.5, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 5.3, "fibra": 0.1, "sodio": 1.8},
        {"nome": "Refrigerante, tipo água tônica", "calorias": 30.8, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 8.0, "fibra": 0, "sodio": 8.3},
        {"nome": "Refrigerante, tipo cola", "calorias": 33.5, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 8.7, "fibra": 0, "sodio": 7.1},
        {"nome": "Refrigerante, tipo guaraná", "calorias": 38.7, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 10.0, "fibra": 0, "sodio": 9.0},
        {"nome": "Refrigerante, tipo laranja", "calorias": 45.6, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 11.8, "fibra": 0, "sodio": 9.3},
        {"nome": "Refrigerante, tipo limão", "calorias": 39.7, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 10.3, "fibra": 0, "sodio": 8.8},
        {"nome": "Omelete, de queijo", "calorias": 268.0, "proteina": 15.6, "gordura_total": 22.0, "carboidratos": 0.4, "fibra": 0, "sodio": 216.1},
        {"nome": "Ovo, de codorna, inteiro, cru", "calorias": 176.9, "proteina": 13.7, "gordura_total": 12.7, "carboidratos": 0.8, "fibra": 0, "sodio": 129.0},
        {"nome": "Ovo, de galinha, clara, cozida/10minutos", "calorias": 59.4, "proteina": 13.4, "gordura_total": 0.1, "carboidratos": 0.0, "fibra": 0, "sodio": 180.5},
        {"nome": "Ovo, de galinha, gema, cozida/10minutos", "calorias": 352.7, "proteina": 15.9, "gordura_total": 30.8, "carboidratos": 1.6, "fibra": 0, "sodio": 44.9},
        {"nome": "Ovo, de galinha, inteiro, cozido/10minutos", "calorias": 145.7, "proteina": 13.3, "gordura_total": 9.5, "carboidratos": 0.6, "fibra": 0, "sodio": 145.9},
        {"nome": "Ovo, de galinha, inteiro, cru", "calorias": 143.1, "proteina": 13.0, "gordura_total": 8.9, "carboidratos": 1.6, "fibra": 0, "sodio": 167.9},
        {"nome": "Ovo, de galinha, inteiro, frito", "calorias": 240.2, "proteina": 15.6, "gordura_total": 18.6, "carboidratos": 1.2, "fibra": 0, "sodio": 166.1},
        {"nome": "Achocolatado, pó", "calorias": 401.0, "proteina": 4.2, "gordura_total": 2.2, "carboidratos": 91.2, "fibra": 3.9, "sodio": 64.8},
        {"nome": "Açúcar, cristal", "calorias": 386.8, "proteina": 0.3, "gordura_total": 0, "carboidratos": 99.6, "fibra": 0, "sodio": 0},
        {"nome": "Açúcar, mascavo", "calorias": 368.6, "proteina": 0.8, "gordura_total": 0.1, "carboidratos": 94.5, "fibra": 0, "sodio": 25.2},
        {"nome": "Açúcar, refinado", "calorias": 386.6, "proteina": 0.3, "gordura_total": 0, "carboidratos": 99.5, "fibra": 0, "sodio": 12.2},
        {"nome": "Chocolate, meio amargo", "calorias": 474.9, "proteina": 4.9, "gordura_total": 29.9, "carboidratos": 62.4, "fibra": 4.9, "sodio": 8.9},
        {"nome": "Cocada branca", "calorias": 448.8, "proteina": 1.1, "gordura_total": 13.6, "carboidratos": 81.4, "fibra": 3.6, "sodio": 29.0},
        {"nome": "Doce, de abóbora, cremoso", "calorias": 198.9, "proteina": 0.9, "gordura_total": 0.2, "carboidratos": 54.6, "fibra": 2.3, "sodio": 0},
        {"nome": "Geléia, mocotó, natural", "calorias": 106.1, "proteina": 2.1, "gordura_total": 0.1, "carboidratos": 24.2, "fibra": 0, "sodio": 42.7},
        {"nome": "Glicose de milho", "calorias": 292.1, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 79.4, "fibra": 0, "sodio": 58.9},
        {"nome": "Maria mole", "calorias": 301.2, "proteina": 3.8, "gordura_total": 0.2, "carboidratos": 73.6, "fibra": 0.7, "sodio": 15.3},
        {"nome": "Maria mole, coco queimado", "calorias": 306.6, "proteina": 3.9, "gordura_total": 0.1, "carboidratos": 75.1, "fibra": 0.6, "sodio": 14.3},
        {"nome": "Marmelada", "calorias": 257.2, "proteina": 0.4, "gordura_total": 0.1, "carboidratos": 70.8, "fibra": 4.1, "sodio": 10.9},
        {"nome": "Mel, de abelha", "calorias": 309.2, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 84.0, "fibra": 0, "sodio": 6.0},
        {"nome": "Melado", "calorias": 296.5, "proteina": 0.0, "gordura_total": 0.0, "carboidratos": 76.6, "fibra": 0, "sodio": 4.0},
        {"nome": "Quindim", "calorias": 411.3, "proteina": 4.7, "gordura_total": 24.4, "carboidratos": 46.3, "fibra": 3.2, "sodio": 27.4},
        {"nome": "Rapadura", "calorias": 352.0, "proteina": 1.0, "gordura_total": 0.1, "carboidratos": 90.8, "fibra": 0, "sodio": 21.7},
        {"nome": "Café, pó, torrado", "calorias": 418.6, "proteina": 14.7, "gordura_total": 11.9, "carboidratos": 65.8, "fibra": 51.2, "sodio": 1.1},
        {"nome": "Capuccino, pó", "calorias": 417.4, "proteina": 11.3, "gordura_total": 8.6, "carboidratos": 73.6, "fibra": 2.4, "sodio": 382.3},
        {"nome": "Fermento em pó, químico", "calorias": 89.7, "proteina": 0.5, "gordura_total": 0.1, "carboidratos": 43.9, "fibra": 0, "sodio": 10052.4},
        {"nome": "Fermento, biológico, levedura, tablete", "calorias": 89.8, "proteina": 17.0, "gordura_total": 1.5, "carboidratos": 7.7, "fibra": 4.2, "sodio": 39.6},
        {"nome": "Gelatina, sabores variados, pó", "calorias": 380.2, "proteina": 8.9, "gordura_total": 0, "carboidratos": 89.2, "fibra": 0, "sodio": 234.9},
        {"nome": "Shoyu", "calorias": 60.9, "proteina": 3.3, "gordura_total": 0.3, "carboidratos": 11.6, "fibra": 0, "sodio": 5024.2},
        {"nome": "Tempero a base de sal", "calorias": 21.3, "proteina": 2.7, "gordura_total": 0.3, "carboidratos": 2.1, "fibra": 0.6, "sodio": 32560.0},
        {"nome": "Azeitona, preta, conserva", "calorias": 194.2, "proteina": 1.2, "gordura_total": 20.3, "carboidratos": 5.5, "fibra": 4.6, "sodio": 1566.7},
        {"nome": "Azeitona, verde, conserva", "calorias": 136.9, "proteina": 0.9, "gordura_total": 14.2, "carboidratos": 4.1, "fibra": 3.8, "sodio": 1347.2},
        {"nome": "Chantilly, spray, com gordura vegetal", "calorias": 315.0, "proteina": 0.5, "gordura_total": 27.3, "carboidratos": 16.9, "fibra": 0, "sodio": 109.7},
        {"nome": "Acarajé", "calorias": 289.2, "proteina": 8.3, "gordura_total": 19.9, "carboidratos": 19.1, "fibra": 9.4, "sodio": 304.9},
        {"nome": "Arroz carreteiro", "calorias": 153.8, "proteina": 10.8, "gordura_total": 7.1, "carboidratos": 11.6, "fibra": 1.5, "sodio": 1621.7},
        {"nome": "Baião de dois, arroz e feijão-de-corda", "calorias": 135.7, "proteina": 6.2, "gordura_total": 3.2, "carboidratos": 20.4, "fibra": 5.1, "sodio": 93.3},
        {"nome": "Barreado", "calorias": 165.0, "proteina": 18.3, "gordura_total": 9.5, "carboidratos": 0.2, "fibra": 0.1, "sodio": 47.6},
        {"nome": "Bife à cavalo, com contra filé", "calorias": 291.2, "proteina": 23.7, "gordura_total": 21.1, "carboidratos": 0.0, "fibra": 0, "sodio": 82.9},
        {"nome": "Bolinho de arroz", "calorias": 273.5, "proteina": 8.0, "gordura_total": 8.3, "carboidratos": 41.7, "fibra": 2.7, "sodio": 58.9},
        {"nome": "Camarão à baiana", "calorias": 100.8, "proteina": 7.9, "gordura_total": 6.0, "carboidratos": 3.2, "fibra": 0.4, "sodio": 84.8},
        {"nome": "Charuto, de repolho", "calorias": 78.2, "proteina": 6.8, "gordura_total": 1.1, "carboidratos": 10.1, "fibra": 1.5, "sodio": 12.1},
        {"nome": "Cuscuz, de milho, cozido com sal", "calorias": 113.5, "proteina": 2.2, "gordura_total": 0.7, "carboidratos": 25.3, "fibra": 2.1, "sodio": 247.7},
        {"nome": "Cuscuz, paulista", "calorias": 142.1, "proteina": 2.6, "gordura_total": 4.6, "carboidratos": 22.5, "fibra": 2.4, "sodio": 235.7},
        {"nome": "Cuxá, molho", "calorias": 80.1, "proteina": 5.6, "gordura_total": 3.6, "carboidratos": 5.7, "fibra": 3.0, "sodio": 1344.3},
        {"nome": "Dobradinha", "calorias": 124.5, "proteina": 19.8, "gordura_total": 4.4, "carboidratos": 0.0, "fibra": 0, "sodio": 28.8},
        {"nome": "Estrogonofe de carne", "calorias": 173.1, "proteina": 15.0, "gordura_total": 10.8, "carboidratos": 3.0, "fibra": 0, "sodio": 122.8},
        {"nome": "Estrogonofe de frango", "calorias": 156.8, "proteina": 17.6, "gordura_total": 8.0, "carboidratos": 2.6, "fibra": 0, "sodio": 99.5},
        {"nome": "Feijão tropeiro mineiro", "calorias": 151.6, "proteina": 10.2, "gordura_total": 6.8, "carboidratos": 19.6, "fibra": 3.6, "sodio": 365.1},
        {"nome": "Frango, com açafrão", "calorias": 112.8, "proteina": 9.7, "gordura_total": 6.2, "carboidratos": 4.1, "fibra": 0.2, "sodio": 28.8},
        {"nome": "Macarrão, molho bolognesa", "calorias": 119.5, "proteina": 4.9, "gordura_total": 0.9, "carboidratos": 22.5, "fibra": 0.8, "sodio": 8.9},
        {"nome": "Maniçoba", "calorias": 134.2, "proteina": 10.0, "gordura_total": 8.7, "carboidratos": 3.4, "fibra": 2.2, "sodio": 406.7},
        {"nome": "Quibebe", "calorias": 86.3, "proteina": 8.6, "gordura_total": 2.7, "carboidratos": 6.6, "fibra": 1.7, "sodio": 246.6},
        {"nome": "Salada, de legumes, com maionese", "calorias": 96.1, "proteina": 1.1, "gordura_total": 7.0, "carboidratos": 8.9, "fibra": 2.2, "sodio": 228.4},
        {"nome": "Salada, de legumes, cozida no vapor", "calorias": 35.4, "proteina": 2.0, "gordura_total": 0.3, "carboidratos": 7.1, "fibra": 2.5, "sodio": 2.5},
        {"nome": "Salpicão, de frango", "calorias": 147.9, "proteina": 13.9, "gordura_total": 7.8, "carboidratos": 4.6, "fibra": 0.4, "sodio": 248.3},
        {"nome": "Sarapatel", "calorias": 123.0, "proteina": 18.5, "gordura_total": 4.4, "carboidratos": 1.1, "fibra": 0, "sodio": 215.6},
        {"nome": "Tabule", "calorias": 57.5, "proteina": 2.0, "gordura_total": 1.2, "carboidratos": 10.6, "fibra": 2.1, "sodio": 1.2},
        {"nome": "Tacacá", "calorias": 46.9, "proteina": 7.0, "gordura_total": 0.4, "carboidratos": 3.4, "fibra": 0.2, "sodio": 1349.1},
        {"nome": "Tapioca, com manteiga", "calorias": 347.8, "proteina": 0.1, "gordura_total": 10.9, "carboidratos": 63.6, "fibra": 0, "sodio": 157.5},
        {"nome": "Tucupi, com pimenta-de-cheiro", "calorias": 27.2, "proteina": 2.1, "gordura_total": 0.3, "carboidratos": 4.7, "fibra": 0.2, "sodio": 5.1},
        {"nome": "Vaca atolada", "calorias": 144.9, "proteina": 5.1, "gordura_total": 9.3, "carboidratos": 10.1, "fibra": 2.3, "sodio": 25.6},
        {"nome": "Vatapá", "calorias": 254.9, "proteina": 6.0, "gordura_total": 23.2, "carboidratos": 9.7, "fibra": 1.7, "sodio": 879.9},
        {"nome": "Virado à paulista", "calorias": 306.9, "proteina": 10.2, "gordura_total": 25.6, "carboidratos": 14.1, "fibra": 2.2, "sodio": 345.5},
        {"nome": "Yakisoba", "calorias": 112.8, "proteina": 7.5, "gordura_total": 2.6, "carboidratos": 18.3, "fibra": 1.1, "sodio": 793.8},
        {"nome": "Amendoim, grão, cru", "calorias": 544.1, "proteina": 27.2, "gordura_total": 43.9, "carboidratos": 20.3, "fibra": 8.0, "sodio": 0},
        {"nome": "Amendoim, torrado, salgado", "calorias": 605.8, "proteina": 22.5, "gordura_total": 54.0, "carboidratos": 18.7, "fibra": 7.8, "sodio": 375.7},
        {"nome": "Ervilha, em vagem", "calorias": 88.1, "proteina": 7.5, "gordura_total": 0.5, "carboidratos": 14.2, "fibra": 9.7, "sodio": 0},
        {"nome": "Ervilha, enlatada, drenada", "calorias": 73.8, "proteina": 4.6, "gordura_total": 0.4, "carboidratos": 13.4, "fibra": 5.1, "sodio": 372.1},
        {"nome": "Feijão, carioca, cozido", "calorias": 76.4, "proteina": 4.8, "gordura_total": 0.5, "carboidratos": 13.6, "fibra": 8.5, "sodio": 1.8},
        {"nome": "Feijão, carioca, cru", "calorias": 329.0, "proteina": 20.0, "gordura_total": 1.3, "carboidratos": 61.2, "fibra": 18.4, "sodio": 0},
        {"nome": "Feijão, fradinho, cozido", "calorias": 78.0, "proteina": 5.1, "gordura_total": 0.6, "carboidratos": 13.5, "fibra": 7.5, "sodio": 1.0},
        {"nome": "Feijão, fradinho, cru", "calorias": 339.2, "proteina": 20.2, "gordura_total": 2.4, "carboidratos": 61.2, "fibra": 23.6, "sodio": 10.3},
        {"nome": "Feijão, jalo, cozido", "calorias": 92.7, "proteina": 6.1, "gordura_total": 0.5, "carboidratos": 16.5, "fibra": 13.9, "sodio": 0.5},
        {"nome": "Feijão, jalo, cru", "calorias": 327.9, "proteina": 20.1, "gordura_total": 0.9, "carboidratos": 61.5, "fibra": 30.3, "sodio": 24.6},
        {"nome": "Feijão, preto, cozido", "calorias": 77.0, "proteina": 4.5, "gordura_total": 0.5, "carboidratos": 14.0, "fibra": 8.4, "sodio": 1.9},
        {"nome": "Feijão, preto, cru", "calorias": 323.6, "proteina": 21.3, "gordura_total": 1.2, "carboidratos": 58.8, "fibra": 21.8, "sodio": 0},
        {"nome": "Feijão, rajado, cozido", "calorias": 84.7, "proteina": 5.5, "gordura_total": 0.4, "carboidratos": 15.3, "fibra": 9.3, "sodio": 0.7},
        {"nome": "Feijão, rajado, cru", "calorias": 325.8, "proteina": 17.3, "gordura_total": 1.2, "carboidratos": 62.9, "fibra": 24.0, "sodio": 13.7},
        {"nome": "Feijão, rosinha, cozido", "calorias": 67.9, "proteina": 4.5, "gordura_total": 0.5, "carboidratos": 11.8, "fibra": 4.8, "sodio": 2.1},
        {"nome": "Feijão, rosinha, cru", "calorias": 337.0, "proteina": 20.9, "gordura_total": 1.3, "carboidratos": 62.2, "fibra": 20.6, "sodio": 24.1},
        {"nome": "Feijão, roxo, cozido", "calorias": 76.9, "proteina": 5.7, "gordura_total": 0.5, "carboidratos": 12.9, "fibra": 11.5, "sodio": 1.5},
        {"nome": "Feijão, roxo, cru", "calorias": 331.4, "proteina": 22.2, "gordura_total": 1.2, "carboidratos": 60.0, "fibra": 33.8, "sodio": 9.8},
        {"nome": "Grão-de-bico, cru", "calorias": 354.7, "proteina": 21.2, "gordura_total": 5.4, "carboidratos": 57.9, "fibra": 12.4, "sodio": 5.2},
        {"nome": "Guandu, cru", "calorias": 344.1, "proteina": 19.0, "gordura_total": 2.1, "carboidratos": 64.0, "fibra": 21.3, "sodio": 1.6},
        {"nome": "Lentilha, cozida", "calorias": 92.6, "proteina": 6.3, "gordura_total": 0.5, "carboidratos": 16.3, "fibra": 7.9, "sodio": 1.2},
        {"nome": "Lentilha, crua", "calorias": 339.1, "proteina": 23.2, "gordura_total": 0.8, "carboidratos": 62.0, "fibra": 16.9, "sodio": 0},
        {"nome": "Paçoca, amendoim", "calorias": 486.9, "proteina": 16.0, "gordura_total": 26.1, "carboidratos": 52.4, "fibra": 7.3, "sodio": 166.8},
        {"nome": "Pé-de-moleque, amendoim", "calorias": 503.2, "proteina": 13.2, "gordura_total": 28.0, "carboidratos": 54.7, "fibra": 3.4, "sodio": 16.3},
        {"nome": "Soja, farinha", "calorias": 404.0, "proteina": 36.0, "gordura_total": 14.6, "carboidratos": 38.4, "fibra": 20.2, "sodio": 5.8},
        {"nome": "Soja, extrato solúvel, natural, fluido", "calorias": 39.1, "proteina": 2.4, "gordura_total": 1.6, "carboidratos": 4.3, "fibra": 0.4, "sodio": 56.5},
        {"nome": "Soja, extrato solúvel, pó", "calorias": 458.9, "proteina": 35.7, "gordura_total": 26.2, "carboidratos": 28.5, "fibra": 7.3, "sodio": 83.5},
        {"nome": "Soja, queijo (tofu)", "calorias": 64.5, "proteina": 6.6, "gordura_total": 4.0, "carboidratos": 2.1, "fibra": 0.8, "sodio": 1.2},
        {"nome": "Tremoço, cru", "calorias": 381.3, "proteina": 33.6, "gordura_total": 10.3, "carboidratos": 43.8, "fibra": 32.3, "sodio": 3.3},
        {"nome": "Tremoço, em conserva", "calorias": 120.6, "proteina": 11.1, "gordura_total": 3.8, "carboidratos": 12.4, "fibra": 14.4, "sodio": 1808.8},
        {"nome": "Amêndoa, torrada, salgada", "calorias": 580.7, "proteina": 18.6, "gordura_total": 47.3, "carboidratos": 29.5, "fibra": 11.6, "sodio": 278.5},
        {"nome": "Castanha-de-caju, torrada, salgada", "calorias": 570.2, "proteina": 18.5, "gordura_total": 46.3, "carboidratos": 29.1, "fibra": 3.7, "sodio": 125.0},
        {"nome": "Castanha-do-Brasil, crua", "calorias": 643.0, "proteina": 14.5, "gordura_total": 63.5, "carboidratos": 15.1, "fibra": 7.9, "sodio": 0.7},
        {"nome": "Coco, cru", "calorias": 406.5, "proteina": 3.7, "gordura_total": 42.0, "carboidratos": 10.4, "fibra": 5.4, "sodio": 15.3},
        {"nome": "Farinha, de mesocarpo de babaçu, crua", "calorias": 328.8, "proteina": 1.4, "gordura_total": 0.2, "carboidratos": 79.2, "fibra": 17.9, "sodio": 12.5},
        {"nome": "Gergelim, semente", "calorias": 583.5, "proteina": 21.2, "gordura_total": 50.4, "carboidratos": 21.6, "fibra": 11.9, "sodio": 2.6},
        {"nome": "Linhaça, semente", "calorias": 495.1, "proteina": 14.1, "gordura_total": 32.3, "carboidratos": 43.3, "fibra": 33.5, "sodio": 8.7},
        {"nome": "Pinhão, cozido", "calorias": 174.4, "proteina": 3.0, "gordura_total": 0.7, "carboidratos": 43.9, "fibra": 15.6, "sodio": 0.9},
        {"nome": "Pupunha, cozida", "calorias": 218.5, "proteina": 2.5, "gordura_total": 12.8, "carboidratos": 29.6, "fibra": 4.3, "sodio": 0.9},
        {"nome": "Noz, crua", "calorias": 620.1, "proteina": 14.0, "gordura_total": 59.4, "carboidratos": 18.4, "fibra": 7.2, "sodio": 4.6},
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
