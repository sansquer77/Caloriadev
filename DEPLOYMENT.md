# 🚀 Guia de Deployment - Caloria Dev v2.6

## 📄 Instalação Local

### 1. Pré-requisitos

```bash
# Python 3.10+
python --version

# pip (gerenciador de pacotes)
pip --version
```

### 2. Clonar Repositório

```bash
git clone https://github.com/sansquer77/Caloriadev.git
cd Caloriadev
```

### 3. Criar Virtual Environment

```bash
# Linux/Mac
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
.\venv\Scripts\activate
```

### 4. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 5. Configurar Variáveis de Ambiente

```bash
cp .env.example .env
```

Editar `.env`:

```env
# Perplexity API
PERPLEXITY_API_KEY=seu_token_aqui

# Database (padrão: SQLite local)
DATABASE_URL=sqlite:///./caloria.db

# Streamlit
STREAMLIT_SERVER_PORT=8501
STREAMLIT_LOGGER_LEVEL=info
```

### 6. Executar App

```bash
streamlit run app.py
```

Acesse: `http://localhost:8501`

---

## 📨 Deployment no Heroku

### 1. Preparar Projeto

```bash
# Cria arquivo Procfile
echo "web: streamlit run app.py" > Procfile

# Cria arquivo setup.sh (required by Heroku)
cat > setup.sh << 'EOF'
mkdir -p ~/.streamlit/
echo "[server]
headless = true
port = $PORT
enableXsrfProtection = false
" > ~/.streamlit/config.toml
EOF

chmod +x setup.sh
```

### 2. Fazer Commit

```bash
git add .
git commit -m "chore: Prepare for Heroku deployment"
git push origin main
```

### 3. Deploy no Heroku

```bash
# Login
heroku login

# Criar app
heroku create caloriadev

# Setar variáveis de ambiente
heroku config:set PERPLEXITY_API_KEY=seu_token
heroku config:set DATABASE_URL=postgresql://...(se usar Postgres)

# Deploy
git push heroku main

# Ver logs
heroku logs --tail
```

---

## 🛠️ Troubleshooting

### Erro 1: ImportError em off_cache_manager.py

**Sintoma:**
```
ImportError: from db import get_db_session, OpenFoodFactsCache
ModuleNotFoundError: No module named 'db'
```

**Solução:**

```bash
# 1. Verificar que está no diretório correto
pwd  # Deve mostrar .../Caloriadev

# 2. Verificar que venv está ativo
which python  # Deve mostrar venv/bin/python

# 3. Reinstalar dependências
pip install -r requirements.txt --force-reinstall

# 4. Testar imports
python -c "from db import SessionLocal, Meal; print('OK')"
```

### Erro 2: Database Lock

**Sintoma:**
```
OperationalError: database is locked
```

**Solução:**

```bash
# 1. Deletar arquivo de lock (se existir)
rm caloria.db-journal

# 2. Garantir que apenas uma instância do app está rodando
pkill -f "streamlit run"

# 3. Usar conexoes com timeout
# Editar db.py:
engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30  # 30 segundos de timeout
    }
)
```

### Erro 3: Perplexity API não responde

**Sintoma:**
```
ERROR: Failed to connect to Perplexity API
ConnectionError: Max retries exceeded
```

**Solução:**

```python
# Em api_perplexity.py, aumentar timeout:
response = requests.post(
    url,
    json=payload,
    timeout=60  # 60 segundos em vez de 30
)

# Ou usar retry com exponential backoff:
import time
max_retries = 3
for attempt in range(max_retries):
    try:
        response = requests.post(...)
        return response
    except requests.exceptions.Timeout:
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # 1, 2, 4 segundos
            time.sleep(wait_time)
        else:
            raise
```

### Erro 4: Memoria insuficiente

**Sintoma:**
```
MemoryError: Unable to allocate X GiB
```

**Solução:**

```bash
# 1. Verificar memória disponível
free -h  # Linux
mem  # macOS
wmic logicaldisk get size  # Windows

# 2. Limpar cache do Streamlit
streamlit cache clear

# 3. Limpar banco de dados
sqlite3 caloria.db "VACUUM;"

# 4. Reduzir tamanho do cache OFF
python -c "from off_cache_manager import cleanup_off_cache; cleanup_off_cache(days_inactive=30)"
```

### Erro 5: Perplexity retorna JSON inválido

**Sintoma:**
```
json.JSONDecodeError: Expecting value: line 1 column 1
```

**Solução:**

```python
# Em meal_parser.py, adicionar validação:
try:
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        parsed = json.loads(json_str)
    else:
        # Tenta parse simples
        return parse_meal_description_simple(description)
except json.JSONDecodeError:
    # Fallback
    return parse_meal_description_simple(description)
```

---

## 🧪 Testes Locais

### 1. Testar Imports

```bash
python -c "
from db import SessionLocal, Meal, MealItem, User
from api_perplexity import analyze_meal_by_description
from meal_parser import parse_and_analyze_meal
from nutrition_analysis import get_nutrition_analysis
print('✅ Todos os imports OK')
"
```

### 2. Testar Banco de Dados

```bash
python -c "
from db import init_db, SessionLocal, User, Meal
init_db()
db = SessionLocal()
print(f'✅ Banco inicializado')
db.close()
"
```

### 3. Testar Parser

```bash
python -c "
from meal_parser import parse_meal_description

items = parse_meal_description('100g espaghetti, bife, alface, pudim')
print(f'✅ Items parsed: {len(items)}')
for item in items:
    print(f'  - {item[\"item\"]}: {item[\"quantity\"]}')
"
```

### 4. Executar Testes Unitários

```bash
pytest tests/ -v
```

---

## 📊 Monitoramento em Produção

### 1. Logs

```bash
# Ver logs do Heroku
heroku logs --tail

# Salvar logs localmente
heroku logs > app.log
```

### 2. Health Check

Adicionar endpoint de health check:

```python
# Em app.py ou em um arquivo separado health.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "2.6",
        "timestamp": datetime.utcnow().isoformat()
    }
```

### 3. Backup do Banco

```bash
# Backup local
cp caloria.db caloria.db.backup.$(date +%Y%m%d_%H%M%S)

# Fazer upload para cloud (AWS S3, Google Cloud Storage, etc)
aws s3 cp caloria.db s3://backup-bucket/caloria.db
```

---

## 📚 Variáveis de Ambiente Recomendadas

```env
# Perplexity
PERPLEXITY_API_KEY=sk-xxx  # OBRIGATÓRIO

# Database
DATABASE_URL=sqlite:///./caloria.db  # Padrão
# Para produção, considere PostgreSQL:
# DATABASE_URL=postgresql://user:password@localhost/caloriadev

# Streamlit
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_LOGGER_LEVEL=info
STREAMLIT_CLIENT_TOOLBAR_MODE=viewer

# App
APP_ENV=production  # ou development
DEBUG=False

# Logging
LOG_LEVEL=INFO
```

---

## 🚀 Performance Tips

### 1. Cache de Queries

```python
@st.cache_data(ttl=3600)  # Cache por 1 hora
def get_meals_for_period(start_date, end_date):
    db = SessionLocal()
    meals = db.query(Meal).filter(...).all()
    db.close()
    return meals
```

### 2. Lazy Loading

```python
# Não carregar todos os dados de uma vez
page = st.number_input("Página", min_value=1)
page_size = 50
offset = (page - 1) * page_size

meals = db.query(Meal).offset(offset).limit(page_size).all()
```

### 3. Índices de Banco

```sql
-- Criar índices para queries frequentes
CREATE INDEX idx_meals_user_date ON meals(user_id, date);
CREATE INDEX idx_meal_items_meal ON meal_items(meal_id);
CREATE INDEX idx_off_cache_accessed ON open_food_facts_cache(accessed_at);
```

---

## 📄 Documentos Relacionados

- [CHANGELOG_v26.md](./CHANGELOG_v26.md) - Detalhes das features v2.6
- [README.md](./README.md) - Guia geral do projeto
- [CHANGES.md](./CHANGES.md) - Histórico de mudanças

---

## 👋 Support

Para mais suporte:

- 📧 Abrir issue no GitHub
- 💬 Discussões
- 🔍 Buscar em [Troubleshooting](#troubleshooting) acima

---

**Desenvolvido com ❤️ | Rastreador Nutricional Inteligente**
