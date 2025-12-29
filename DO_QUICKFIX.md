# 🚀 Quick Fix Checklist - DigitalOcean ImportError

**⚠️ IMPORTANTE:** Se seu app não está funcionando no DigitalOcean, siga este checklist.

---

## 📄 Passo 1: Verificar Status do App

### No DigitalOcean Dashboard:

```
1. Abra: cloud.digitalocean.com
2. Clique em: Apps (menu lateral esquerdo)
3. Selecione: caloriadev
4. Verifique o status:

   ✅ DEPLOYED - App está rodando (OK)
   🔄 BUILDING - App está compilando (aguarde 5-10 min)
   ❌ ERROR - Erro no build (ver logs)
```

---

## 📇 Passo 2: Ver Logs de Erro

```
1. Clique em: Seu App > Logs
2. Procure por:
   ❌ ImportError
   ❌ ModuleNotFoundError
   ❌ KeyError
   ❌ OperationalError
3. Copie a mensagem completa
4. Vá para a seção de Troubleshooting abaixo
```

---

## 📄 Passo 3: Verificar Variáveis de Ambiente

```
1. Clique em: Seu App > Settings
2. Scroll para: Environment Variables
3. Procure por:
   ✅ PERPLEXITY_API_KEY = sk-xxxxx
   ✅ DATABASE_URL = sqlite:///./caloria.db (ou postgresql://...)

Se falta:
   - Clique em: Edit
   - Adicione as variáveis
   - Clique em: Save
   - Faça novo deploy (ver Passo 5)
```

---

## 🔄 Passo 4: Verificar requirements.txt

```
No seu local ou direto no GitHub:

1. Abra: requirements.txt
2. Verifique se tem:

   streamlit>=1.28.0
   SQLAlchemy>=2.0.0
   pandas>=2.1.0
   requests>=2.31.0
   python-dotenv>=1.0.0

Se falta alguma:
   - Adicione a linha
   - Faça commit e push
   - DigitalOcean fará deploy automático
```

---

## 🚀 Passo 5: Forçar Novo Deploy

### Opção A: Push no GitHub (recomendado)

```bash
# No seu terminal local
git add .
git commit -m "fix: Deploy para corrigir ImportError"
git push origin main

# Aguarde 5-10 minutos
# DigitalOcean fará deploy automático
```

### Opção B: Deploy Manual

```
1. Clique em: Seu App > Deploy
2. Clique em: Deploy Latest Commit
3. Aguarde ~5 minutos
```

---

## 🛠️ Troubleshooting Rápido

### Erro: "ModuleNotFoundError: No module named 'db'"

❌ **Causa:** requirements.txt faltando dependências

📄 **Solução:**
```bash
# 1. Verificar requirements.txt
cat requirements.txt

# 2. Se falta "SQLAlchemy", adicione:
echo "SQLAlchemy>=2.0.0" >> requirements.txt

# 3. Commit e push
git add requirements.txt
git commit -m "fix: Adicionar SQLAlchemy ao requirements"
git push origin main

# 4. Aguarde novo deploy
```

---

### Erro: "KeyError: 'PERPLEXITY_API_KEY'"

❌ **Causa:** Variável de ambiente não setada

📄 **Solução:**
```
1. Seu App > Settings > Environment Variables
2. Clique em: Edit
3. Procure por: PERPLEXITY_API_KEY
4. Se não existe:
   - Clique em: Add Variable
   - Key: PERPLEXITY_API_KEY
   - Value: seu_token_aqui (sk-xxxxx)
5. Clique em: Save
6. Aguarde novo deploy (~3 min)
```

---

### Erro: "OperationalError: database is locked"

❌ **Causa:** SQLite com problemas de concorrência

📄 **Solução (Rápida):**
```
1. Seu App > Settings
2. Clique em: Trigger Rebuild
3. Aguarde 10 minutos
```

📄 **Solução (Definitiva - Recomendada):**
```
1. Criar PostgreSQL no DigitalOcean:
   - Clique em: Databases
   - Create > PostgreSQL
   - Escolha plano mínimo ($15)
   - Aguarde 2-5 min
   - Copie a Connection String

2. Atualizar variável de ambiente:
   - Seu App > Settings > Environment Variables
   - Edit > DATABASE_URL
   - Cole a connection string do PostgreSQL
   - Save

3. Deploy automático
   - Aguarde ~3 minutos
```

---

### Erro: "Port Already in Use"

❌ **Causa:** Conflito de porta

📄 **Solução:**
```
1. Seu App > Settings
2. Verifique: HTTP Port = 8501
3. Se diferente, altere para 8501
4. Trigger Rebuild
```

---

### Erro: "Build Failed - Timeout"

❌ **Causa:** Build demorando muito

📄 **Solução:**
```
1. Seu App > Settings
2. Instance Type > Escolha plano maior
3. Trigger Rebuild

Ou simplificar requirements.txt:
   - Remova pacotes não usados
   - Use versões específicas
```

---

## 📇 Passo 6: Testar App

```
1. Seu App > Live App
2. Clique no link (https://seu-app-xxxx.ondigitalocean.app)
3. Teste:
   - Página carrega? ✅ OK
   - Menu funciona? ✅ OK
   - Registrar refeição funciona? ✅ OK
   - API Perplexity responde? ✅ OK
```

---

## 📚 Ver Logs em Tempo Real

```
1. Seu App > Logs
2. Escolha: Time Range = Last 1 hour
3. Observe mensagens:
   ✅ [INFO] Streamlit server started
   ✅ [INFO] Meal saved successfully
   ⚠️ [WARNING] API timeout
   ❌ [ERROR] Database connection failed
```

---

## 📚 Checklist Final

- [ ] Status do app = DEPLOYED
- [ ] Nenhum erro nos Logs
- [ ] PERPLEXITY_API_KEY setada
- [ ] DATABASE_URL setada
- [ ] requirements.txt atualizado
- [ ] App responde no navegador
- [ ] Pode registrar refeição
- [ ] Perplexity retorna dados
- [ ] Banco salva dados

✅ Se tudo marcado: **App está funcionando!**

---

## 👋 Ainda com Problema?

1. 📇 **Lê o guia completo:** [DIGITALOCEAN_GUIDE.md](./DIGITALOCEAN_GUIDE.md)
2. 📚 **Veja logs detalhados:** Seu App > Logs > Copy everything
3. 📧 **Abra issue no GitHub:** com os logs completos
4. 💬 **Discord/Suporte:** DigitalOcean Support

---

**Desenvolvido com ❤️ | Caloria Dev v2.6**
