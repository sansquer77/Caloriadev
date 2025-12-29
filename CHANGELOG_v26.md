# 🚀 CHANGELOG v2.6 - Parser Inteligente & Análise Nutricional

**Data:** 29/12/2024  
**Versão:** 2.6  
**Status:** ✅ Pronto para uso

---

## 📋 Resumo das Mudanças

Implementão de 3 funcionalidades principais:

1. ✅ **Parser Inteligente de Refeições** - Quebra descrição em itens individuais
2. ✅ **Itens Individuais no Banco** - Rastreamento granular de nutrientes
3. ✅ **Análise Nutricional com Perplexity** - Insights semanal/mensal

---

## 🎯 Funcionalidade 1: Parser Inteligente

### Arquivo: `meal_parser.py` (NOVO)

**Objetivo:** Quebrar descrição completa de refeição em itens separados

**Antes:**
```
"100g espaghetti a alho e óleo, 1 bife médio à milanesa, alface, pudim"
  ↓ (uma única consulta à API)
  ↓ (impreciso - pudim pode não ser detectado corretamente)
```

**Depois:**
```
"100g espaghetti a alho e óleo, 1 bife médio à milanesa, alface, pudim"
  ↓
  ✅ Parse com Perplexity (quebra em itens)
  ↓
  ✅ Item 1: "Espaghetti a alho e óleo" (100g)
  ✅ Item 2: "Bife médio à milanesa" (150g estimado)
  ✅ Item 3: "Alface americana" (80g estimado)
  ✅ Item 4: "Pudim de leite" (50g estimado)
  ↓
  ✅ Consulta ISOLADA para cada item
  ↓
  ✅ Nutrientes precisos (açúcares do pudim detectados!)
```

### Funções Principais:

```python
# 1. Quebrar em itens
items = parse_meal_description(
    "100g espaghetti, bife, alface, pudim"
)
# Retorna: [
#   {'item': 'Espaghetti a alho e óleo', 'quantity': '100g'},
#   {'item': 'Bife médio', 'quantity': '150g'},
#   ...
# ]

# 2. Analisar cada item
result = analyze_meal_items(items)
# Retorna: {
#   'items': [{item, quantity, nutrients}, ...],
#   'totals': {calories, protein, fiber, ...}
# }

# 3. Pipeline completo
result = parse_and_analyze_meal(
    "100g espaghetti a alho e óleo, 1 bife médio..."
)
```

### Benefícios:

- ✅ **Precisão:** Cada item analisado isoladamente
- ✅ **Açúcares:** Pudim agora detectado corretamente!
- ✅ **Fibras:** Cálculos mais precisos
- ✅ **Rastreamento:** Cada item salvo individualmente
- ✅ **Fallback:** Se Perplexity falhar, faz parse simples

---

## 💾 Funcionalidade 2: Itens Individuais no Banco

### Schema do Banco (atualizado)

**Nova tabela: `meal_items`**

```sql
CREATE TABLE meal_items (
    id INTEGER PRIMARY KEY,
    meal_id INTEGER FOREIGN KEY,  -- Liga à refeição
    
    -- Item
    item_name VARCHAR(255),        -- Ex: "Espaghetti a alho e óleo"
    quantity VARCHAR(50),          -- Ex: "100g"
    
    -- Nutrientes DO ITEM
    calories FLOAT,
    protein FLOAT,
    carbs FLOAT,
    sugar FLOAT,
    fiber FLOAT,
    ... (10 nutrientes)
    
    -- Ordem
    order INTEGER,
    created_at DATETIME
);
```

### Estrutura de Dados:

```
Meal (refeição consolidada)
├─ date: "2024-12-29"
├─ meal_type: "almoco"
├─ description: "100g espaghetti, bife, alface, pudim"
├─ calories: 555 (soma dos itens)
├─ protein: 42
├─ fiber: 8.5
└─ items: [
    {
        item_name: "Espaghetti a alho e óleo",
        quantity: "100g",
        calories: 150,
        protein: 5,
        fiber: 1.8
    },
    {
        item_name: "Bife médio à milanesa",
        quantity: "150g",
        calories: 280,
        protein: 28,
        fiber: 0
    },
    ...
]
```

### Vantagens:

- 📚 **Rastreamento Granular:** Ver exatamente o que foi comido
- 📋 **Relatórios Detalhados:** Quebrar por item se necessário
- 📑 **Histórico Preciso:** Saber quais itens mais aparecem
- 📝 **Notas:** Adicionar observações por item futuramente

---

## 📊 Funcionalidade 3: Análise Nutricional

### Arquivo: `nutrition_analysis.py` (NOVO)

#### 1. Análise com Perplexity

```python
analysis = get_nutrition_analysis(
    period_data={
        'days_count': 7,
        'calories': 14000,
        'protein': 525,
        'fiber': 175,
        ...
    },
    period_type='semanal'  # ou 'mensal'
)
```

**Saída:** String com análise nutricional personalizadá

```
### ANÁLISE NUTRICIONAL - SEMANAL

**Médias Diárias:**
- Calorias: 2000 kcal
- Proteínas: 75g (15% das calorias)
- Carboidratos: 250g (50% das calorias)
- Fibras: 25g
- Açúcares: 20g

**PONTOS POSITIVOS:**
✅ Fibras: Excelente (25g/dia) - Continue assim!
✅ Açúcares: Ótimo (<25g/dia) - Benéfico para saúde
✅ Proteínas: Ótimo (75g/dia) - Muito bom

**ÁREAS DE MELHORIA:**
🙋 Sódio: Procure reduzir um pouco (2500mg vs. 2300mg recomendado)
🙋 Carboidratos: Ligeiramente elevado - considere reduzir 10%

**RECOMENDAÇÕES:**
1. Manter o consumo de fibras - está excelente
2. Reduzir sal em preparos - busque usar mais ervas
3. Aumentar proporção de proteínas em sobremesas

Geral: Seu padrão nutricional está MUÍTO BOM! 🎆
```

#### 2. Comparação com Recomendações

```python
comparison = compare_with_recommendations(period_data)

# Retorna: {
#   'protein': {'value': 75, 'target': 70, 'status': 'good', 'percentage': 107},
#   'fiber': {'value': 25, 'target': 25, 'status': 'good', 'percentage': 100},
#   'sugar': {'value': 20, 'target': 25, 'status': 'excellent', 'percentage': 80},
#   ...
# }
```

### Prompts Customizados:

O Perplexity recebe prompt especializado:

```
Analise o seguinte padrão nutricional de SEMANAL (uma pessoa real em diário) e dê feedback construtivo:

- Médias diárias: 2000 kcal, 75g protein, 250g carbs, 25g fiber
- Recomendações: 1500-2500 cal, 45-65% carbs, <25g açúcar, 25-35g fiber

Critério: Feedback REALISTA (não perfeito), identifique 3 pontos bons + 2-3 melhorias, dê 1-2 ações fáceis.
Seja breve (max 200 palavras), amigável e construtivo.
```

---

## 🎨 Atualizações na Interface

### Tela 1: Registrar Refeição

```
┌─ Registrar Nova Refeição ─────────────────────────────────┐
│                                                              │
│ Data: [29/12/2024]  Tipo: [Almoço]  Local: [Casa]          │
│                                                              │
│ Descrição da Refeição:                                   │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │ 100g espaghetti a alho e óleo, 1 bife médio à         │ │
│ │ milanesa, alface temperada, pudim de leite               │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│ [🔍 Analisar Refeição]  ← Novo botão com parsing         │
│                                                              │
├─────────── RESULTADO (itens identificados) ────────────────│
│                                                              │
│ 🍝 Espaghetti a alho e óleo (100g)                         │
│    Calorias: 150 kcal | Proteínas: 5g                     │
│                                                              │
│ 🥩 Bife médio à milanesa (150g)                          │
│    Calorias: 280 kcal | Proteínas: 28g                    │
│                                                              │
│ 🥬 Alface americana (80g)                                   │
│    Calorias: 15 kcal | Fibras: 1.5g                        │
│                                                              │
│ 🍮 Pudim de leite (50g)  ← Detectado corretamente!         │
│    Calorias: 110 kcal | Açúcares: 18.5g  ← Agora preciso! │
│                                                              │
├─────────── RESUMO TOTAL DA REFEIÇÃO ──────────────────────│
│                                                              │
│ 🔥 Calorias  │ 🧠 Proteínas │ 🍞 Carboidratos │ 🌾 Fibras │
│ 555 kcal    │ 42g          │ 65g            │ 8.5g     │
│                                                              │
│ [💾 Salvar Refeição]                                      │
└──────────────────────────────────────────────────────────────┘
```

### Tela 2: Histórico

```
Data  | Refeição | Calorias | Proteínas | Carbs | Fibras | Local
------|-----------|----------|-----------|-------|--------|-------
29/12 | Almoço   | 555      | 42g       | 65g   | 8.5g   | Casa
29/12 | Cafe      | 320      | 12g       | 45g   | 3.2g   | Casa
28/12 | Jantar    | 720      | 52g       | 80g   | 10g    | Rest.
```

### Tela 3: Relatórios (NOVO)

```
┌─ RELATÓRIO SEMANAL ───────────────────────────────────────┐
│                                                            │
│ 🔥 Calorias      │ 🧠 Proteínas │ 🍞 Carbs │ 🌾 Fibras      │
│ 2000 kcal/dia    │ 75g/dia      │ 250g/dia │ 25g/dia        │
│ Total: 14000     │ Total: 525g  │ Total... │ Total: 175g    │
│                                                            │
├─ ANÁLISE NUTRICIONAL (PERPLEXITY) ────────────────────────┤
│                                                            │
│ ### ANÁLISE - SEMANAL                                    │
│                                                            │
│ **PONTOS POSITIVOS:**                                    │
│ ✅ Fibras: Excelente (25g/dia) - Continue assim!         │
│ ✅ Açúcares: Ótimo (<25g/dia) - Benéfico!               │
│ ✅ Proteínas: Ótimas (75g) - Método hipertrofia ok      │
│                                                            │
│ **ÁREAS DE MELHORIA:**                                   │
│ 🎯 Sódio: Ligeiramente elevado (2500 vs 2300mg recom.)    │
│ 🎯 Carboidratos: Considere reduzir 10% em final de dia   │
│                                                            │
│ **AÇÕES RECOMENDADAS:**                                 │
│ 1. Reduzir sal nos preparos - use mais temperos          │
│ 2. Manter fibras no nível atual - excelente!             │
│ 3. Aumentar proteínas em lanches intermediários          │
│                                                            │
│ Seu padrão está MUÍTO BOM! 🎆                           │
│                                                            │
├─ COMPARAÇÃO COM RECOMENDAÇÕES ────────────────────────────┤
│                                                            │
│ Nutriente     | Valor  | Meta  | Percentual | Status      │
│ Protein       | 75.0   | 70.0  | 107%       | ✅          │
│ Fiber         | 25.0   | 25.0  | 100%       | ✅          │
│ Sugar         | 20.0   | 25.0  | 80%        | ✅ Excelente│
│ Sodium        | 238.0  | 230.0 | 103%       | ⚠️ Moderado │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 🔄 Fluxo Completo

```
Usuário digita refeição
      ↓
  "100g espaghetti, bife, alface, pudim"
      ↓
  meal_parser.py
      ↓
  parse_meal_description() → Perplexity quebra em itens
      ↓
  [
    {item: "Espaghetti...", quantity: "100g"},
    {item: "Bife...", quantity: "150g"},
    ...
  ]
      ↓
  analyze_meal_items() → Consulta cada item isoladamente
      ↓
  result = {
    items: [{item, quantity, nutrients}, ...],
    totals: {calories, protein, fiber, ...}
  }
      ↓
  Exibir itens + totais
      ↓
  Usuário clica "Salvar"
      ↓
  Salvar no banco:
    - Meal (refeição consolidada)
    - MealItem[] (cada item)
      ↓
  ✅ Pronto para relatórios
```

---

## 📈 Relatórios (Semanal/Mensal)

```
1. Buscar todas as Meal do período
2. Agregar nutrientes (somas)
3. Calcular médias diárias
4. Enviar para Perplexity para análise
5. Comparar com recomendações
6. Exibir métricas + insights + comparação
```

---

## 🚀 Como Usar

### 1. Registrar Refeição

```
1. Clique em "Registrar Refeição"
2. Preencha data, tipo e local (opcional)
3. Descreva tudo que comeu (separado por vírgulas)
4. Clique em "🔍 Analisar Refeição"
5. Revise os itens identificados
6. Clique em "💾 Salvar Refeição"
```

### 2. Ver Histórico

```
1. Clique em "Histórico"
2. Escolha período e filtros
3. Veja tabela com todos os itens
4. Veja resumo de nutrientes do período
```

### 3. Gerar Relatório

```
1. Clique em "Relatórios"
2. Escolha "Semanal" ou "Mensal"
3. Veja métricas + análise Perplexity
4. Veja comparação com recomendações
```

---

## ⚠️ Notas Importantes

### 1. Performance
- Parser com Perplexity: ~2-3 segundos
- Análise de 4 itens: ~8-12 segundos (parallelizável no futuro)
- Busca de histórico: instantânea

### 2. Qualidade dos Dados
- Quanto melhor a descrição, melhor o parse
- Incluir quantidades é importante
- Se não tiver quantidade, será estimado

### 3. Fallbacks
- Se Perplexity cair: usa parse simples (por vírgulas)
- Se análise falhar: salva de qualquer forma
- Se relatório falhar: mostra dados básicos

### 4. Storage
- Cada item individual usa ~200 bytes no DB
- 100 refeições (400 itens) = ~80 KB
- Escalabilidade: 10k refeições = ~2 MB (sem problema)

---

## 📁 Arquivos Modificados

### Novos:
- ✅ `meal_parser.py` - Parser inteligente
- ✅ `nutrition_analysis.py` - Análise nutricional

### Modificados:
- ✅ `db.py` - Nova tabela MealItem
- ✅ `app.py` - Integração completa

---

## 📚 Estrutura do Projeto Atualizada

```
Caloriadev/
├─ app.py                    (atualizado)
├─ db.py                     (atualizado)
├─ api_perplexity.py         (existente)
├─ off_cache_manager.py      (v2.5)
├─ meal_parser.py            (NOVO - v2.6)
├─ nutrition_analysis.py     (NOVO - v2.6)
├─ requirements.txt
├─ .env.example
├─ CHANGELOG_v26.md          (este arquivo)
└─ README.md
```

---

## 🧪 Próximos Passos Sugeridos

### Curto Prazo (v2.7):
- [ ] Paralelizar análise de itens (mais rápido)
- [ ] Cache de itens analisados
- [ ] Export de relatórios (PDF/Excel)
- [ ] Notas por item

### Médio Prazo (v2.8):
- [ ] Dashboard com gráficos interativos
- [ ] Metas personalizadas por nutriente
- [ ] Alertas de nutrientes
- [ ] Sincronização com MyFitnessPal

### Longo Prazo (v3.0):
- [ ] App mobile
- [ ] Reconhecimento de fotos
- [ ] Integração com wearables
- [ ] Machine learning para previsões

---

## 👋 Support

Com dúvidas ou sugestões?

- 📧 GitHub Issues
- 💬 Discussões
- 💾 Database backup: `caloria.db`

---

**Desenvolvido com ❤️ | Rastreador Nutricional Inteligente**
