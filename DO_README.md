# 🚀 Caloria Dev v2.6 - DigitalOcean App Platform

## ⚠️ IMPORTANTE: ImportError Fix

Se seu app não está funcionando, **comece aqui:**

### 🔋 Quick Checklist (5 minutos)

📄 **Leia:** [DO_QUICKFIX.md](./DO_QUICKFIX.md)

Este arquivo tem um checklist passo-a-passo para:
- Verificar status do app
- Ver logs de erro
- Adicionar variáveis de ambiente
- Forçar novo deploy
- Troubleshooting rápido

---

## 🎩 O que foi fixado?

### Problema
```
ModuleNotFoundError: No module named 'db'
ImportError: from db import get_db_session
```

### Solução

✅ **1. Corrigir imports**
- `off_cache_manager.py`: usar `SessionLocal()` ao invés de `get_db_session()`
- `app.py`: remover imports desnecessarios

✅ **2. Adicionar error handling**
- Try/catch em todas as operações do banco
- Logging de erros
- Conexões sempre fechadas

✅ **3. Atualizar requirements**
- Todas as dependências listadas
- Versões fixadas

✅ **4. Criar configuração DigitalOcean**
- `app.yaml` com settings corretos
- Variáveis de ambiente
- Run command otimizado

---

## 📧 Commits Realizados

```
✅ 0a71790 - fix: Corrigir imports em off_cache_manager.py
✅ ba01a6f - fix: Remover imports desnecessarios do app.py
✅ 819f81b - deps: Atualizar requirements.txt
✅ 4c434f3 - config: Adicionar app.yaml para DigitalOcean
✅ a84caaf - docs: Guia completo DigitalOcean
✅ 51f1960 - docs: Quick fix checklist
```

---

## 🚀 Deploy no DigitalOcean

### Opção 1: Deploy Automático (Recomendado)

```bash
# Push para main
git add .
git commit -m "fix: Deploy para DigitalOcean"
git push origin main

# DigitalOcean detecta automaticamente!
# Acompanhe em: cloud.digitalocean.com > Apps > caloriadev
# Aguarde 5-10 minutos
```

### Opção 2: Deploy Manual

```
1. Cloud.digitalocean.com
2. Apps > caloriadev
3. Deploy > Deploy Latest Commit
4. Aguarde ~5 minutos
```

---

## 📊 Verificar Se Funcionou

```
1. Seu App > Live App
2. Clique no link (https://seu-app-xxxx.ondigitalocean.app)
3. Teste:
   ✅ Página carrega?
   ✅ Menu funciona?
   ✅ Pode registrar refeição?
   ✅ Parser quebra em itens?
   ✅ Relatório mostra fibras?
```

---

## 🛠️ Troubleshooting

### Cenario 1: Build Failed com ImportError

```
Leia: DO_QUICKFIX.md > Erro: ModuleNotFoundError
✅ Solucao: Adicionar SQLAlchemy ao requirements.txt
```

### Cenario 2: App rodando mas sem API

```
Leia: DO_QUICKFIX.md > Erro: KeyError: PERPLEXITY_API_KEY
✅ Solucao: Adicionar PERPLEXITY_API_KEY nas Environment Variables
```

### Cenario 3: Database locked

```
Leia: DO_QUICKFIX.md > Erro: OperationalError
✅ Solucao: Usar PostgreSQL ou resetar database
```

### Para Erros Mais Complicados

```
Leia: DIGITALOCEAN_GUIDE.md (guia completo)
Tem:
- Configuração inicial
- Variáveis de ambiente
- 5 erros comuns + soluções
- Monitoramento
- Backup & Restore
```

---

## 📚 Estrutura do Projeto

```
Caloriadev/
├─ app.py                 # App principal (corrigido)
├─ db.py                  # Modelos SQLAlchemy (atualizado)
├─ meal_parser.py         # Parser inteligente (novo)
├─ nutrition_analysis.py  # Análise Perplexity (novo)
├─ off_cache_manager.py   # Cache OFF (FIXADO)
├─ api_perplexity.py      # API do Perplexity
├─
├─ app.yaml              # Config DigitalOcean (NOVO)
├─ requirements.txt       # Dependências (ATUALIZADO)
├─
├─ DO_README.md           # Este arquivo
├─ DO_QUICKFIX.md         # Checklist rápido
├─ DIGITALOCEAN_GUIDE.md  # Guia completo
├─ DEPLOYMENT.md          # Deployment geral
├─ CHANGELOG_v26.md       # Features v2.6
├─ README.md              # README principal
└─ caloria.db             # Banco de dados (SQLite)
```

---

## 🚀 Features v2.6 (Novas)

### Parser Inteligente 🍴
```
Descreve refeição: "100g espaghetti, bife, alface, pudim"
↓
Perplexity quebra em itens:
- Espaghetti (100g)
- Bife (150g)
- Alface (80g)
- Pudim (50g) ← Agora detectado!
```

### Itens Individuais 💺
```
Cada item salvo separadamente no banco
Permite relatórios granulares
✅ Rastreamento preciso
```

### Análise Nutricional 🦪
```
Relatórios semanal/mensal com:
- Métricas consolidadas
- Insights do Perplexity
- Comparação com recomendações
- Agora com FIBRAS! 🌾
```

---

## 📚 Variáveis de Ambiente (Obrigatórias)

```
Apps > Settings > Environment Variables

OBRIGATÓRIA:
- PERPLEXITY_API_KEY = sk-xxxxx
  (Obter em: https://www.perplexity.ai/api)

PADRÃO (já setadas):
- DATABASE_URL = sqlite:///./caloria.db
- STREAMLIT_SERVER_HEADLESS = true
- STREAMLIT_CLIENT_TOOLBAR_MODE = viewer
```

---

## 📈 Logs & Monitoramento

```
Apps > Seu App > Logs

Procure por:
✅ [INFO] Streamlit server started
✅ [INFO] Application started
❌ [ERROR] ImportError
❌ [ERROR] ModuleNotFoundError
❌ [ERROR] KeyError
```

---

## 📧 Contato & Suporte

Se problema não resolver:

1. **Checar Documentos**
   - [DO_QUICKFIX.md](./DO_QUICKFIX.md) (5 min)
   - [DIGITALOCEAN_GUIDE.md](./DIGITALOCEAN_GUIDE.md) (30 min)

2. **DigitalOcean Support**
   - Apps > Seu App > Support
   - Ou support@digitalocean.com

3. **GitHub Issues**
   - https://github.com/sansquer77/Caloriadev/issues
   - Descreva o erro com logs

---

**Desenvolvido com ❤️ | Caloria Dev v2.6**

⚡ **PRÓXIMO PASSO:** [Leia DO_QUICKFIX.md](./DO_QUICKFIX.md)
