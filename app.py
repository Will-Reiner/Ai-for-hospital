import os
import time
import streamlit as st
from google import genai
from dotenv import load_dotenv
from database import init_db, get_schema, execute_query

load_dotenv()

st.set_page_config(page_title="Chat Hospitalar", page_icon="🏥", layout="centered")
st.title("🏥 Chat com Banco de Dados Hospitalar")

# Inicializa o banco de dados
init_db()

# Configura a API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.warning("Configure a variável GEMINI_API_KEY no arquivo .env para começar.")
    st.stop()

client = genai.Client(api_key=api_key)

# Sidebar com dados de exemplo
with st.sidebar:
    st.header("📋 Dados do Banco")
    if st.button("Ver dados de exemplo"):
        st.session_state.mostrar_dados = not st.session_state.get("mostrar_dados", False)

    if st.session_state.get("mostrar_dados", False):
        st.subheader("Pacientes")
        st.dataframe(execute_query("SELECT * FROM pacientes"), use_container_width=True)
        st.subheader("Médicos")
        st.dataframe(execute_query("SELECT * FROM medicos"), use_container_width=True)
        st.subheader("Consultas")
        st.dataframe(execute_query("SELECT * FROM consultas"), use_container_width=True)

# Estado do chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibe histórico
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("🔍 SQL executado"):
                st.code(msg["sql"], language="sql")
        if "dataframe" in msg:
            with st.expander("📊 Dados retornados"):
                st.dataframe(msg["dataframe"])

# Input do usuário
if pergunta := st.chat_input("Faça uma pergunta sobre o banco de dados..."):
    st.session_state.messages.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            schema = get_schema()

            # Monta histórico de conversa para contexto
            historico = ""
            for msg in st.session_state.messages[:-1]:  # exclui a pergunta atual (já adicionada)
                if msg["role"] == "user":
                    historico += f"Usuário: {msg['content']}\n"
                elif msg["role"] == "assistant":
                    historico += f"Assistente: {msg['content']}\n"

            contexto_historico = ""
            if historico:
                contexto_historico = f"""Histórico da conversa (use como contexto para entender referências como "ele", "ela", "isso", "o mesmo", etc.):
{historico}
"""

            # Prompt 1: Text-to-SQL
            prompt_sql = f"""Você é um assistente que converte perguntas em SQL.
Dado o esquema:
{schema}

{contexto_historico}Pergunta atual: {pergunta}
Retorne APENAS o código SQL, sem markdown, sem explicação."""

            try:
                # st.info("🔄 Enviando pergunta para gerar SQL...")
                response_sql = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_sql)
                
                # st.success("✅ Resposta SQL recebida")
                # with st.expander("🐛 DEBUG: response_sql"):
                #     st.write(response_sql)
                
                sql = response_sql.text.strip()

                # Remove possíveis backticks residuais
                sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()

                # st.info("🔄 Executando consulta SQL...")
                df = execute_query(sql)
                resultado = df.to_string(index=False) if not df.empty else "Nenhum resultado encontrado."
                
                # with st.expander("🐛 DEBUG: resultado"):
                #     st.write(resultado)

                # Aguarda para evitar rate limit
                # st.info("⏳ Aguardando 2 segundos para evitar rate limit...")
                time.sleep(2)

                # Prompt 2: Resposta em linguagem natural
                prompt_resposta = f"""{contexto_historico}Dado a pergunta atual: {pergunta}
E o resultado da consulta SQL: {resultado}
Forneça uma resposta natural e clara em português. Considere o histórico da conversa para dar uma resposta contextualizada."""

                # with st.expander("🐛 DEBUG: prompt_resposta"):
                #     st.write(prompt_resposta)

                # st.info("🔄 Enviando para gerar resposta em linguagem natural...")
                response_nl = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_resposta)
                
                # st.success("✅ Resposta NL recebida")
                # with st.expander("🐛 DEBUG: response_nl"):
                #     st.write(response_nl)
                
                resposta = response_nl.text.strip()

                st.markdown(resposta)
                # with st.expander("🔍 SQL executado"):
                #     st.code(sql, language="sql")
                # with st.expander("📊 Dados retornados"):
                #     st.dataframe(df)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": resposta,
                    "sql": sql,
                    "dataframe": df,
                })

            except Exception as e:
                erro = f"Erro ao processar a pergunta: {e}"
                st.error(erro)
                st.session_state.messages.append({"role": "assistant", "content": erro})
