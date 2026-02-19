# Manual de Execução

## 1. Criar o ambiente virtual

```bash
python -m venv venv
```

## 2. Ativar o ambiente virtual

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

## 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

## 4. Configurar a API Key

Crie um arquivo `.env` na raiz do projeto com o conteúdo:

```
GEMINI_API_KEY=sua-chave-aqui
```

Gere sua chave em: https://aistudio.google.com/apikeys

## 5. Rodar a aplicação

```bash
streamlit run app.py
```

A aplicação abrirá no navegador em `http://localhost:8501`.
