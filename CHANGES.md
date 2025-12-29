# 📄 Resumo de Mudanças - v2.5

**Data:** 29/12/2024  
**Foco:** Consolidação do banco de dados único + Melhoria de visualização nutricionais

---

## 🎯 Principais Mudanças

### 1. **Consolidação do Cache Open Food Facts em SQLite** ✅

#### O que mudou:
- ❌ **Removido:** `OFF_CACHE.json` (arquivo separado em disco)
- ✅ **Adicionado:** Tabela `open_food_facts_cache` no `caloria.db`

#### Benefícios:
- 📦 **Um único banco de dados** para backup (caloria.db com tudo)
- 🔒 **ACID compliance** - transações seguras
- 📊 **Sem limite de tamanho** - JSON era limitado a ~1500 itens
- 🔄 **Sincronização automática** com backup
- 📈 **Rastreamento de acesso** melhorado
- 🧹 **Limpeza automática** (LRU 90 dias)

#### Arquivos Novos:

**`off_cache_manager.py`** (REESCRITO)  
```python
# Agora usa SQLite ao invés de JSON
- add_to_cache(food_data) → Adiciona/atualiza em SQL
- get_from_cache(food_name, barcode) → Busca rápida
- get_off_cache_stats() → Estatísticas completas
- cleanup_off_cache(days_inactive=90) → Limpeza LRU
- get_cache_health() → Status do cache
```

**`off_cache_migration.py`** (NOVO)  
```python
# Migração segura de dados legados
- migrate_off_cache_to_db() → Importa OFF_CACHE.json existente
- rollback_migration() → Reverte se necessário
- legacy_cache_exists() → Detecta arquivo antigo
```

#### Tabela SQL Criada:

```sql
CREATE TABLE open_food_facts_cache (
    id INTEGER PRIMARY KEY,
    food_name VARCHAR(255) -- Nome normalizado
    barcode VARCHAR(20) UNIQUE -- Código de barras
    product_name VARCHAR(255)
    brand VARCHAR(255)
    
    -- Nutrientes (por 100g)
    calories FLOAT
    protein FLOAT
    fat_total FLOAT
    fat_saturated FLOAT
    carbs FLOAT
    sugar FLOAT
    fiber FLOAT
    sodium FLOAT
    potassium FLOAT
    cholesterol FLOAT
    
    -- Metadados
    nutrition_grade VARCHAR(5) -- A-E
    serving_size VARCHAR(50)
    image_url TEXT
    
    -- Rastreamento
    cached_at DATETIME
    accessed_at DATETIME -- Último acesso (para LRU)
    hits INTEGER -- Contador de acessos
    include_in_backup BOOLEAN -- Controle de backup
);

-- Índices para performance
CREATE INDEX idx_off_food_name ON open_food_facts_cache(food_name);
CREATE INDEX idx_off_barcode ON open_food_facts_cache(barcode);
CREATE INDEX idx_off_accessed_at ON open_food_facts_cache(accessed_at);
```

---

### 2. **Adição de Fibras no Histórico** 📊

#### Mudanças em `app.py`:

**Função `show_history()`:**
```python
# Antes: sem coluna de fibras
display_df = df[[
    'date', 'meal_type', 'description', 'calories', 'protein', 
    'carbs', 'fat_total', 'sugar', 'location_name'  # ❌ sem fibras
]]

# Depois: com coluna de fibras
display_df = df[[
    'date', 'meal_type', 'description', 'calories', 'protein', 
    'carbs', 'fat_total', 'sugar', 'fiber', 'location_name'  # ✅ com fibras
]].rename(columns={
    'fiber': 'Fibras (g)'
})
```

**Estatísticas Rápidas** (nova seção):
```python
# Exibe métricas do histórico
- Média de Calorias: X kcal
- Média de Proteínas: X g
- Média de Carboidratos: X g
- Média de Fibras: X g  ← NOVO
- Total de Refeições: X
```

**Resumo Semanal** (atualizado):
```python
# Antes: sem fibras
st.write(f"- Calorias: {weekly_macros.get('calories', 0):.1f} kcal")
st.write(f"- Proteínas: {weekly_macros.get('protein', 0):.1f} g")
st.write(f"- Carboidratos: {weekly_macros.get('carbs', 0):.1f} g")

# Depois: com fibras
st.write(f"- 🔥 Calorias: {weekly_macros.get('calories', 0):.1f} kcal")
st.write(f"- 🥩 Proteínas: {weekly_macros.get('protein', 0):.1f} g")
st.write(f"- 🍞 Carboidratos: {weekly_macros.get('carbs', 0):.1f} g")
st.write(f"- 🌾 Fibras: {weekly_macros.get('fiber', 0):.1f} g")  # ← NOVO
```

**Resumo de Relatórios** (atualizado):
```python
# Adicionado métricas de fibras
st.metric("🌾 Fibras Total", f"{macros.get('fiber', 0):.1f}g")
st.metric("🌾 Média/dia", f"{macros.get('fiber', 0)/days:.1f}g")
```

---

## 📊 Estrutura do Banco de Dados

```
caloria.db (arquivo único)
├── users (autenticação)
├── meals (refeições do usuário)
├── taco_foods (referência TACO - opcional)
└── open_food_facts_cache (✨ NOVO - cache consolidado)
    ├── Compartilhado entre todos os usuários
    ├── Auto-limpeza (90 dias)
    └── Rastreamento de acessos
```

**Backup agora é simples:**
```bash
# Antes: 2 arquivos
cp caloria.db backup.db
cp OFF_CACHE.json backup_cache.json

# Depois: 1 arquivo!
cp caloria.db backup.db
```

---

## 🔄 Migração de Dados Legados

Se você tem um `OFF_CACHE.json` existente:

```python
from off_cache_migration import migrate_off_cache_to_db

# Executa automaticamente na primeira execução
stats = migrate_off_cache_to_db()
print(f"✅ {stats['imported']} itens migrados")

# Arquivo legado é movido para .backup (segurança)
```

---

## 📱 Interface (UI Updates)

### Resumo Diário:
```
┌─ RESUMO DIÁRIO ──────────────────────────────┐
│ 🔥 Calorias   │ 🥩 Proteínas │ 🍞 Carbs │ 🌾 Fibras │
│ 2000.0 kcal   │ 75.0 g       │ 250.0 g  │ 25.0 g    │
└───────────────────────────────────────────────┘
```

### Histórico:
```
Data  | Refeição | Descrição | Calorias | ... | Fibras (g) | Local
------|----------|-----------|----------|-----|------------|-------
29/12 | Almoço   | Arroz...  | 1200.0   | ... | 8.5        | Casa
```

### Relatórios:
```
Fibras Total: 175.0 g
Média/dia:     25.0 g
```

---

## 🚀 Como Usar

### Inicialização Automática:
```python
from db import init_db

init_db()  # Cria tabelas e índices automaticamente
```

### Adicionar ao Cache:
```python
from off_cache_manager import add_to_cache

add_to_cache({
    'food_name': 'Maçã Red Delicious',
    'barcode': '7891234567890',
    'product_name': 'Maçã Red Delicious Orgânica',
    'calories': 52.0,
    'fiber': 2.4,
    # ... outros nutrientes
})
```

### Buscar no Cache:
```python
from off_cache_manager import get_from_cache

# Por nome
item = get_from_cache(food_name='Maçã')

# Por barcode
item = get_from_cache(barcode='7891234567890')
```

### Limpeza Automática:
```python
from off_cache_manager import cleanup_off_cache, get_off_cache_health

# Check saúde
health = get_off_cache_health()
print(f"Status: {health['status']}")  # healthy | warning | critical

# Limpar itens inativos
removed = cleanup_off_cache(days_inactive=90)
print(f"Removidos: {removed} itens")
```

---

## 🧪 Testes Recomendados

```python
# 1. Migração
from off_cache_migration import migrate_off_cache_to_db
stats = migrate_off_cache_to_db()
assert stats['success'] == True
assert stats['imported'] > 0

# 2. Cache
from off_cache_manager import add_to_cache, get_from_cache
add_to_cache({'food_name': 'Test Item', 'calories': 100})
item = get_from_cache(food_name='Test Item')
assert item['calories'] == 100

# 3. Limpeza
from off_cache_manager import cleanup_off_cache
removed = cleanup_off_cache(days_inactive=0)  # Remove tudo
assert removed >= 0
```

---

## 📚 Documentação Relacionada

- `db.py` - Modelos SQLAlchemy
- `off_cache_manager.py` - Gerenciador de cache
- `off_cache_migration.py` - Script de migração
- `app.py` - Interface Streamlit (atualizada)

---

## ⚠️ Notas Importantes

1. **Backup Automático**: O arquivo `caloria.db` agora contém TUDO
   - Mantém backup automático em `.bak_{timestamp}`
   - Tamanho estimado: < 500 MB para 10k+ refeições

2. **Compatibilidade**: Não quebra versões anteriores
   - Migração automática detecta `OFF_CACHE.json`
   - Arquivo legado é preservado como `.backup`

3. **Performance**: Índices otimizados
   - Busca por nome: O(log n)
   - Busca por barcode: O(1)
   - Limpeza LRU: O(n) uma vez por dia

4. **Storage**: Cache é opcional em backup
   ```python
   # Incluir/excluir cache do backup
   cached_item.include_in_backup = True  # padrão
   cached_item.include_in_backup = False  # não inclui
   ```

---

## 🎯 Próximas Melhorias

- [ ] Dashboard de análise de fibras
- [ ] Alertas quando fibras < meta
- [ ] Gráficos de evolução de fibras
- [ ] Sincronização com MyFitnessPal API
- [ ] Export de relatórios com fibras

---

**Desenvolvido com ❤️ para melhor rastreamento nutricional**
