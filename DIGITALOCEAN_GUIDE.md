# 🚀 Guia DigitalOcean App Platform - Caloria Dev v2.6

## 📚 Índice

1. [Configuração Inicial](#configuração-inicial)
2. [Variáveis de Ambiente](#variáveis-de-ambiente)
3. [Deploy](#deploy)
4. [Troubleshooting](#troubleshooting)
5. [Monitoramento](#monitoramento)
6. [Backup & Restore](#backup--restore)

---

## 💳 Configuração Inicial

### Pré-requisitos

- ✅ Conta DigitalOcean ativa
- ✅ Repositório GitHub conectado
- ✅ Token PERPLEXITY_API_KEY
- ✅ App Platform habilitado

### Passo 1: Conectar GitHub

1. Abra [DigitalOcean Dashboard](https://cloud.digitalocean.com)
2. Clique em **Apps** (no menu lateral)
3. Clique em **Create App**
4. Escolha **GitHub** como source
5. Clique em **Authorize DigitalOcean**
6. Selecione repositório `sansquer77/Caloriadev`
7. Escolha branch `main`
8. Clique em **Next**

### Passo 2: Configurar App

1. **Nome da App:** `caloriadev`
2. **Runtime:** Selecione a versão recomendada (Streamlit)
3. **Source Directory:** Deixe em branco (raiz)
4. **Build Command:** `pip install -r requirements.txt`
5. **Run Command:** 
   ```
   streamlit run app.py --server.enableCORS=false --server.enableXsrfProtection=false
   ```
6. **HTTP Port:** `8501` (porta padrão Streamlit)
7. **Instance Type:** `Basic` (suficiente para prototipagem)
8. **Instance Count:** `1`

### Passo 3: Variáveis de Ambiente

Clique em **Environment** e adicione:

| Chave | Valor | Escopo |
|-------|-------|--------|
| `PERPLEXITY_API_KEY` | seu_token_aqui | RUN_TIME |
| `DATABASE_URL` | `sqlite:///./caloria.db` | RUN_TIME |
| `STREAMLIT_SERVER_HEADLESS` | `true` | RUN_TIME |
| `STREAMLIT_CLIENT_TOOLBAR_MODE` | `viewer` | RUN_TIME |

---

## 📊 Variáveis de Ambiente

### Obrigatórias

#### `PERPLEXITY_API_KEY` (CRITICAL)
```
Token de acesso da API Perplexity
Formato: sk-xxxxxxxxxxxx
Obtém em: https://www.perplexity.ai/api
```

**Como fazer:
1. Acesse https://www.perplexity.ai/
2. Vá para Settings → API Keys
3. Crie um novo token
4. Copie o valor completo
5. No DigitalOcean Dashboard:
   - Apps → Seu App → Settings → Environment Variables
   - Clique em **Edit**
   - Adicione `PERPLEXITY_API_KEY` com o valor copiado
   - Clique em **Save**

### Opcionais

#### `DATABASE_URL`
```
Conexão do banco de dados
Padrão: sqlite:///./caloria.db

Opciones:
- SQLite (padrão, local): sqlite:///./caloria.db
- PostgreSQL (recomendado prod): postgresql://user:pass@host/db
- MySQL: mysql://user:pass@host/db
```

**Nota:** Se usar PostgreSQL, crie um database no DigitalOcean Databases.

---

## 🚀 Deploy

### Deploy Automático

DigitalOcean detecta mudanças no GitHub e faz deploy automático.

```bash
# 1. Fazer commit
git add .
git commit -m "feat: Nova funcionalidade"

# 2. Push para main
git push origin main

# 3. DigitalOcean detecta automaticamente!
# Acompanhe em: https://cloud.digitalocean.com/apps
```

### Deploy Manual

Acesse Apps → Seu App → **Deploy**

```
✓ Selecione branch main
✓ Clique em "Deploy Latest Commit"
✓ Aguarde ~3-5 minutos
✓ App estará online em: https://seu-app-xxxx.ondigitalocean.app
```

### Verificar Status

```
Apps → Seu App → Activity
✅ BUILD SUCCESSFUL - Compilação OK
✅ DEPLOYMENT SUCCESSFUL - Deploy OK
⏳ BUILDING - Em progresso
❌ ERROR - Erro (ver logs)
```

---

## 🛠️ Troubleshooting

### ❌ Erro 1: ImportError em app.py

**Sintoma:**
```
ModuleNotFoundError: No module named 'db'
Failed to load application
```

**Solução:**

1. **Ver Logs**
   - Apps → Seu App → Logs
   - Procure por "ModuleNotFoundError" ou "ImportError"

2. **Verificar requirements.txt**
   ```bash
   # Certifique-se que requirements.txt tem:
   streamlit>=1.28.0
   SQLAlchemy>=2.0.0
   pandas>=2.1.0
   requests>=2.31.0
   python-dotenv>=1.0.0
   ```

3. **Forçar rebuild**
   - Apps → Seu App → Settings → Trigger rebuild
   - Espere pelo menos 5 minutos

4. **Se ainda erro**
   ```bash
   # No seu local, teste imports
   python -c "from db import SessionLocal; print('OK')"
   
   # Se OK local, pode ser cache do DigitalOcean
   # Aguarde 10 minutos ou delete o app e recrie
   ```

### ❌ Erro 2: Port Already in Use

**Sintoma:**
```
Streamlit can't bind to port 8501
Address already in use
```

**Solução:**

1. **No app.yaml, mudar porta:**
   ```yaml
   http_port: 8501  # Deixar igual
   ```

2. **No run command, especificar:**
   ```
   streamlit run app.py --server.port 8501 --server.address 0.0.0.0
   ```

3. **Redeploy**
   - Faça push para main
   - Aguarde novo deploy

### ❌ Erro 3: PERPLEXITY_API_KEY não encontrada

**Sintoma:**
```
KeyError: 'PERPLEXITY_API_KEY'
os.getenv('PERPLEXITY_API_KEY') returns None
```

**Solução:**

1. **Verificar variável**
   - Apps → Seu App → Settings → Environment
   - Procure por `PERPLEXITY_API_KEY`
   - Se falta, adicione

2. **Cuidado com espaços**
   ```
   ❌ ERRADO: " sk-xxxxx"  (espaço antes)
   ✅ CORRETO: "sk-xxxxx"   (sem espaços)
   ```

3. **Redeploy após adicionar**
   - Clique em **Save**
   - Apps → Deploy → Deploy Latest Commit
   - Aguarde ~5 minutos

4. **Validar token**
   - Acesse seu app no navegador
   - Tente registrar uma refeição
   - Se funcionar, está OK

### ❌ Erro 4: Database Connection Error

**Sintoma:**
```
OperationalError: (sqlite3.OperationalError) unable to open database file
database is locked
```

**Solução:**

1. **Usar PostgreSQL em produção (recomendado)**
   
   No DigitalOcean:
   - Clique em **Databases**
   - **Create → PostgreSQL**
   - Escolha plano padrão ($15/mês)
   - Aguarde criação (~2-5 min)
   - Copie **Connection String**
   
   No app:
   - Apps → Settings → Environment
   - Adicione `DATABASE_URL` = sua connection string
   - Redeploy

2. **Se continuar com SQLite**
   ```bash
   # Limpar database
   rm caloria.db
   git add .
   git commit -m "fix: Reset database"
   git push origin main
   ```

### ❌ Erro 5: App Build Timeout

**Sintoma:**
```
Build failed: Timeout waiting for build to complete
Timeout after 30 minutes
```

**Solução:**

1. **Otimizar requirements.txt**
   - Remove dependências não utilizadas
   - Use versões específicas (ex: `pandas==2.1.0`)

2. **Aumentar build resources**
   - Apps → Settings → Instance Type
   - Escolha um tier maior se disponível

3. **Usar buildpack customizado**
   ```yaml
   buildpacks:
     - name: python
       version: "3.11"
   ```

---

## 📊 Monitoramento

### Logs em Tempo Real

```
Apps → Seu App → Logs

✅ [INFO] Logs aparecem aqui
⚠️ [WARNING] Avisos e alertas
❌ [ERROR] Erros da aplicação
```

### Filtrar Logs

```
Type: Application (padrão)
Component: None (todos)
Time Range: Last hour, Last day, Last week
```

### Tipos de Logs Comuns

```python
# INFO - Operações normais
[INFO] Streamlit server started
[INFO] Cache cleared
[INFO] Meal saved successfully

# WARNING - Avisos
[WARNING] Slow query detected
[WARNING] API timeout (retrying)
[WARNING] Cache size exceeded

# ERROR - Erros
[ERROR] Failed to connect to database
[ERROR] Perplexity API returned 429
[ERROR] ImportError: module not found
```

### Alerts

Configure alerts no DigitalOcean:
1. Apps → Seu App → Settings
2. Scroll para **Alerts**
3. Clique em **Create Alert**
4. Escolha condição (ex: "App crashed")
5. Escolha notificação (email)

---

## 📋 Backup & Restore

### Backup Manual (SQLite)

```bash
# Baixar database do DigitalOcean
doctl apps get-logs caloriadev --follow

# Ou via SSH (se disponível)
doctl compute ssh your-droplet
cp /app/caloria.db ~/caloria.db.backup.$(date +%Y%m%d)
```

### Backup Automático

**Opção 1: GitHub**
```bash
# Seu DB será commitado no repo
git add caloria.db
git commit -m "backup: database snapshot"
git push origin main
```

**Opção 2: S3/Digital Ocean Spaces**
```python
# Adicionar script de backup
import boto3
import shutil
from datetime import datetime

def backup_to_s3():
    # Copiar arquivo
    backup_name = f"caloria_{datetime.now().isoformat()}.db"
    shutil.copy('caloria.db', f'/tmp/{backup_name}')
    
    # Upload para S3
    s3 = boto3.client('s3')
    s3.upload_file(f'/tmp/{backup_name}', 'my-bucket', f'backups/{backup_name}')
```

### Restore

```bash
# 1. Fazer upload do arquivo
git checkout caloria.db.backup.20241229

# 2. Renomear
mv caloria.db.backup.20241229 caloria.db

# 3. Commit e push
git add caloria.db
git commit -m "restore: database from backup"
git push origin main

# 4. DigitalOcean fará deploy automático
```

---

## 📚 Recursos Úties

### DigitalOcean Docs
- [App Platform Docs](https://docs.digitalocean.com/products/app-platform/)
- [Python Apps Guide](https://docs.digitalocean.com/products/app-platform/languages/python/)
- [Streamlit on App Platform](https://docs.digitalocean.com/products/app-platform/how-to/deploy-streamlit/)

### Ferramentas Íteis
```bash
# Instalar doctl (CLI DigitalOcean)
curl -sL https://github.com/digitalocean/doctl/releases/download/v1.98.1/doctl-1.98.1-linux-x64.tar.gz | tar -xz
sudo mv doctl /usr/local/bin

# Conectar com seu token
doctl auth init

# Ver apps
doctl apps list

# Ver logs
doctl apps get-logs your-app-id
```

---

## 👋 Support

Se tiver problemas:

1. 📧 **Email DigitalOcean Support**
   - Apps → Seu App → Support
   - ou support@digitalocean.com

2. 💬 **Discord/Comunidade**
   - Digital Ocean Community
   - Streamlit Discord

3. 💡 **Stack Overflow**
   - Tag: `digitalocean` + `streamlit`

4. 📚 **GitHub Issues**
   - Abrir issue em `sansquer77/Caloriadev`

---

**Desenvolvido com ❤️ | Caloria Dev v2.6**
