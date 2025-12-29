# 🛱 Deployment Seguro em Produção - Caloria Dev v2.6

**STATUS:** App já em produção no DigitalOcean
**OBJETIVO:** Deploy da v2.6 sem quebrar nada

---

## ⚠️ ANTES DE FAZER QUALQUER COMMIT

### Checklist de Segurança (IMPORTANTE!)

- [ ] **Backup do Banco de Dados**
  ```bash
  # Download do banco atual
  # Apps > seu-app > Environment > DATABASE_URL
  # Se SQLite: cp do arquivo caloria.db
  # Se PostgreSQL: export do banco
  ```

- [ ] **Ver Status Atual do App**
  ```
  Apps > seu-app > Live App
  ✅ App respondendo?
  ✅ Sem erros nos logs?
  ```

- [ ] **Anotar Versão Atual**
  ```
  Ver commit atual: git log --oneline | head -1
  Anotar o hash (ex: abc1234)
  ```

- [ ] **Testar Localmente (OPCIONAL)**
  ```bash
  # Se tiver ambiente local
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  streamlit run app.py
  # Testar funcionalidades
  ```

---

## 🚀 PLANO DE DEPLOYMENT

### Fase 1: Preparar Mudanças (30 min)

```bash
# 1. Certificar que está na branch main e atualizado
git branch  # Verificar que está em main
git pull origin main  # Puxar últimas mudanças

# 2. Ver mudanças
git status  # Ver quais arquivos foram alterados
git diff  # Ver o que foi alterado

# 3. Adicionar mudanças
git add .

# 4. Fazer commit com mensagem clara
git commit -m "v2.6: Parser inteligente + itens individuais + análise nutricional"

# 5. Ver o commit
git log --oneline | head -1  # Confirmar commit foi feito
```

### Fase 2: Deploy para DigitalOcean (15 min + 5-10 min de build)

```bash
# 1. Push para main
git push origin main

# 2. DigitalOcean detecta automaticamente
# Pode acompanhar em: cloud.digitalocean.com > Apps > seu-app > Activity

# 3. Esperar pelo build
# Status: BUILDING (amarelo) → DEPLOYED (verde)
# Tempo esperado: 5-10 minutos
```

### Fase 3: Validar Deploy (10 min)

```
1. Abrir: https://seu-app-xxxx.ondigitalocean.app

2. Verificar se funciona:
   ✅ Registrar Refeição
      - Descrever uma refeição completa
      - Clicar em "Analisar Refeição"
      - Deve mostrar itens quebrados
      - Deve mostrar totais
   
   ✅ Histórico
      - Deve aparecer a refeição que registrou
      - Deve mostrar coluna de FIBRAS
   
   ✅ Relatórios
      - Escolher Semanal ou Mensal
      - Deve calcular médias
      - Deve mostrar análise do Perplexity
      - Deve comparar com recomendações

3. Ver logs (Apps > Logs):
   ✅ Procurar por [ERROR]
   ✅ Se houver erro, ver qual
```

### Fase 4: Monitoramento Pós-Deploy (24 horas)

```
1. Acompanhar logs:
   Apps > seu-app > Logs
   Procurar por:
   - [ERROR] ImportError (não deve ter!)
   - [ERROR] ModuleNotFoundError (não deve ter!)
   - [WARNING] (pode ter, não é crise)

2. Se tudo OK:
   ✅ Deployment foi sucesso!

3. Se houver erro:
   Ir para seção "ROLLBACK" abaixo
```

---

## 📚 Alternativos: Deploy com Branch Temporária (MAIS SEGURO)

**Use isso se quer testar antes de colocar em produção:**

```bash
# 1. Criar branch de teste
git checkout -b v2.6-testing

# 2. Fazer todas as mudanças nessa branch
# (Já deve estar com as mudanças)

# 3. Fazer commit
git commit -m "v2.6: Teste em staging"

# 4. Push para a branch
git push origin v2.6-testing

# 5. No DigitalOcean, mudar branch temporária:
# Apps > seu-app > Settings > GitHub > Branch: v2.6-testing
# Trigger Rebuild (App vai usar essa branch)

# 6. Testar tudo
# Se OK:
#    - Voltar branch para main
#    - Fazer merge de v2.6-testing em main
#    - Push para main
# Se erro:
#    - Voltar branch para main no DigitalOcean
#    - Deletar v2.6-testing
#    - Fix os problemas
```

---

## 🔄 ROLLBACK (Se der Problema)

### Cenario 1: App Está quebrado após deploy

```bash
# Opção A: Voltar para commit anterior

# 1. Ver logs de erro
# Apps > seu-app > Logs
# Procurar por [ERROR]

# 2. Copiar hash do último commit bom
git log --oneline | grep -i "v2.5" # ou o commit anterior OK

# 3. Voltar para esse commit
git revert HEAD  # Reverter último commit
git push origin main

# 4. Aguardar novo deploy (5-10 min)
# DigitalOcean fará rollback automático
```

### Cenario 2: Efeitos colaterais (app lento, banco corrompido)

```bash
# 1. Se banco corrompido:
#    - Apps > Databases (se usar PostgreSQL)
#    - Restaurar do backup

# 2. Se app lento:
#    Apps > Settings > Instance Type > aumentar tier
#    Trigger Rebuild

# 3. Se muitos erros:
#    - Fazer rollback (Cenario 1)
#    - Investigar localmente
#    - Fix do problema
#    - Novo deploy
```

### Como evitar problemas

```
✅ SEMPRE fazer teste local primeiro
✅ SEMPRE fazer backup do banco antes
✅ SEMPRE ver logs após deploy
✅ SEMPRE ter plano de rollback
✅ SEMPRE testar funcionalidades principais
```

---

## 🔍 VALIDANDO A V2.6

### Teste 1: Parser Inteligente

```
Registrar Refeição:
  Descrição: 
    "100g espaghetti a alho e óleo, 
     1 bife médio à milanesa, 
     alface temperada, 
     um pedaço pequeno de pudim"
  
  Resultado esperado:
    ✅ 4 itens identificados
    ✅ Cada um com quantidade
    ✅ Pudim com açúcares detectados (18.5g)
    ✅ Total correto
```

### Teste 2: Fibras no Histórico

```
Histórico:
  ✅ Coluna "Fibras (g)" deve aparecer
  ✅ Mostrar valor correto para cada refeição
  ✅ Resumo com total de fibras
```

### Teste 3: Análise Nutricional

```
Relatórios > Semanal/Mensal:
  ✅ Métricas com fibras
  ✅ Análise do Perplexity (insights)
  ✅ Comparação com recomendações
  ✅ Status dos nutrientes
```

---

## 📊 Logs Importantes Pós-Deploy

### Ver Logs em Tempo Real

```
Apps > seu-app > Logs

Procurar por:
✅ [INFO] Application started
✅ [INFO] Streamlit server started
✅ [INFO] Database initialized
✅ [INFO] Meal saved successfully
❌ [ERROR] ImportError
❌ [ERROR] ModuleNotFoundError
❌ [ERROR] Database connection
⚠️ [WARNING] (pode ter alguns)
```

### Filtrar Logs

```
Apps > seu-app > Logs > Filter
  Level: ERROR (se quer ver apenas erros)
  Time Range: Last 1 hour
```

---

## 🚀 CHECKLIST FINAL

### Antes do Commit
- [ ] Backup do banco feito
- [ ] Status atual do app anotado
- [ ] Versão atual (hash do commit) anotada
- [ ] requirements.txt verificado
- [ ] env.example atualizado

### Ao Fazer Commit
- [ ] Mensagem de commit clara
- [ ] Apenas arquivos relevantes adicionados
- [ ] Nenhum arquivo sensível (chaves, senhas)
- [ ] Commit foi bem-sucedido (ver log)

### Após Push
- [ ] Acompanhar build (5-10 min)
- [ ] Ver status em DEPLOYED
- [ ] Testar app em produção
- [ ] Testar registrar refeição
- [ ] Testar relatórios
- [ ] Ver logs de erro (não deve ter!)

### Após Deploy
- [ ] Monitorar por 1 hora
- [ ] Monitorar por 24 horas
- [ ] Tudo funcionando normalmente
- [ ] Nenhum erro nos logs

✅ Se tudo OK: Deployment foi sucesso!

---

## 📇 Commits que Estão Sendo Feitos

```
✅ 0a71790 - fix: Corrigir imports (off_cache_manager)
✅ ba01a6f - fix: Remover imports desnecessarios (app)
✅ 819f81b - deps: Atualizar requirements.txt
✅ 4c434f3 - config: Adicionar app.yaml
✅ a84caaf - docs: Guia DigitalOcean completo
✅ 51f1960 - docs: Quick fix checklist
✅ 314e575 - docs: README DigitalOcean
```

Todos estão prontos. Basta fazer `git push origin main`.

---

## 👋 Se Precisar de Ajuda

1. **App quebrou após deploy:**
   - Ver seção ROLLBACK acima
   - Fazer revert do último commit

2. **Quer testar antes:**
   - Usar branch v2.6-testing
   - Deploy em staging
   - Testar
   - Merge em main se OK

3. **Quer acompanhar deploy:**
   - Apps > seu-app > Activity
   - Ver progresso do build
   - Ver quando fica DEPLOYED

4. **Quer monitorar logs:**
   - Apps > seu-app > Logs
   - Ver [ERROR] ou [WARNING]
   - Acompanhar por 24h

---

**Desenvolvido com ❤️ | Caloria Dev v2.6**

⚡ **PRÓXIMO PASSO:** Fazer `git push origin main` e acompanhar o deploy!
