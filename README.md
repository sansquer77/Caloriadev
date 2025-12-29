# 🍽️ Caloria - Análise Nutricional por Foto

Aplicativo de análise nutricional inteligente que permite fotografar refeições e obter automaticamente informações sobre calorias, macronutrientes e micronutrientes.

## ✨ Funcionalidades

- 📸 **Análise por Foto**: Tire uma foto do seu prato e a IA identifica os alimentos
- ✍️ **Análise por Texto**: Descreva sua refeição manualmente
- 📊 **Análise por Código de Barras**: Escaneie produtos industrializados
- 📊 **Informações Nutricionais Completas**:
  - Calorias
  - Proteínas
  - Carboidratos
  - Açúcares
  - Gorduras (total e saturada)
  - Fibras
  - Sódio
- 📍 **Localização**: Registre onde você fez cada refeição
- 🗺️ **Mapa de Refeições**: Visualize seus locais de alimentação no mapa
- 📈 **Histórico**: Acompanhe seu consumo ao longo do tempo
- 📊 **Resumo Diário/Semanal**: Monitore suas metas nutricionais

## 🛠️ Tecnologias

- **Frontend**: Streamlit
- **Backend**: Python 3.11
- **Banco de Dados**: PostgreSQL (produção) / SQLite (desenvolvimento)
- **IA para Visão**: Google Gemini (análise de fotos)
- **Fontes Nutricionais**:
  - TACO (Tabela Brasileira de Composição de Alimentos) - dados locais
  - Open Food Facts (API gratuita com milhões de produtos)
  - Perplexity AI (fallback para busca de dados nutricionais)

## 🚀 Deploy na Digital Ocean

### Pré-requisitos

1. Conta na [Digital Ocean](https://www.digitalocean.com/)
2. Chave de API da [Perplexity](https://www.perplexity.ai/)
3. Chave de API do [Google Gemini](https://aistudio.google.com/apikey) (para análise de fotos)

### Passo a Passo

1. **Faça fork/clone deste repositório**

2. **Crie um App na Digital Ocean App Platform**
   - Vá para [App Platform](https://cloud.digitalocean.com/apps)
   - Clique em "Create App"
   - Conecte seu repositório GitHub

3. **Configure as Variáveis de Ambiente**
   
   No painel do App, adicione estas variáveis (Settings > App-Level Environment Variables):
   
   | Variável | Descrição |
   |----------|-----------|
   | `PERPLEXITY_API_KEY` | Sua chave da API Perplexity |
   | `GEMINI_KEY` | Sua chave da API Google Gemini (para análise de fotos) |
   | `SECRET_KEY` | Chave secreta para JWT (gere uma aleatória) |
   | `DATABASE_URL` | URL do banco PostgreSQL (fornecida pela DO) |

4. **Adicione um Banco de Dados**
   - Na aba "Components", adicione um Dev Database (PostgreSQL)
   - A variável `DATABASE_URL` será configurada automaticamente

5. **Deploy**
   - Clique em "Deploy to Production"
   - Aguarde o build e deploy finalizar

### Configuração Manual (app.yaml)

Você também pode usar o arquivo `.do/app.yaml` para configurar o app:

```bash
doctl apps create --spec .do/app.yaml
```

## 💻 Desenvolvimento Local

### Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/Caloriadev.git
cd Caloriadev

# Crie um ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
.\venv\Scripts\activate  # Windows

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com suas chaves
```

### Executando

```bash
# Com SQLite (padrão para desenvolvimento)
streamlit run app.py

# Ou defina DATABASE_URL para PostgreSQL
export DATABASE_URL="postgresql://user:pass@localhost:5432/caloria"
streamlit run app.py
```

O app estará disponível em `http://localhost:8501`

## 📁 Estrutura do Projeto

```
Caloriadev/
├── app.py              # Aplicação Streamlit principal
├── api_perplexity.py   # Integração com APIs de IA
├── auth.py             # Autenticação JWT
├── db.py               # Modelos SQLAlchemy
├── models.py           # Dataclasses
├── storage.py          # Operações de banco de dados
├── requirements.txt    # Dependências Python
├── Procfile            # Comando de execução (Heroku/DO)
├── runtime.txt         # Versão do Python
├── .streamlit/
│   └── config.toml     # Configurações do Streamlit
├── .do/
│   └── app.yaml        # Spec do App Platform
└── .env.example        # Exemplo de variáveis de ambiente
```

## 🔑 Obtendo as Chaves de API

### Perplexity AI
1. Acesse [perplexity.ai](https://www.perplexity.ai/)
2. Crie uma conta
3. Vá para API Settings
4. Gere uma nova API Key

## 🍽️ Fontes de Dados Nutricionais

O app usa 3 fontes em cascata para obter dados nutricionais precisos:

1. **TACO** (local) - Tabela Brasileira de Composição de Alimentos com 57 alimentos comuns
2. **Open Food Facts** (API gratuita) - Base de dados colaborativa com milhões de produtos industrializados
3. **Perplexity AI** (fallback) - IA para itens não encontrados nas fontes anteriores

### Código de Barras
O app suporta busca por código de barras de produtos industrializados usando a API Open Food Facts.

## 📱 Uso do App

1. **Cadastre-se** com usuário e senha
2. **Faça login** na sua conta
3. **Tire uma foto** do seu prato ou descreva a refeição
4. **(Opcional)** Adicione sua localização (latitude/longitude)
5. **Clique em Analisar** e veja os nutrientes
6. **Acompanhe** seu histórico e veja o mapa de refeições

## 🗺️ Localização

O app permite registrar a localização de cada refeição. Para isso:

1. Use um app de GPS para obter suas coordenadas
2. Insira latitude e longitude no formulário
3. Opcionalmente, nomeie o local (ex: "Restaurante XYZ")
4. Visualize todos os locais na seção "Mapa de Refeições"
5. Clique para abrir no Google Maps

## 📄 Licença

Este projeto está sob a licença MIT.

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor, abra uma issue ou pull request.
