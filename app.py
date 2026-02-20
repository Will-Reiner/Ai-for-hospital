import io
import os
import streamlit as st
import speech_recognition as sr
from audio_recorder_streamlit import audio_recorder
from openai import OpenAI
from dotenv import load_dotenv
from database import init_db, get_schema, execute_query

load_dotenv()

st.set_page_config(page_title="Chat Hospitalar", page_icon="🏥", layout="centered")
st.title("🏥 Chat com Banco de Dados Hospitalar")

# Inicializa o banco de dados
init_db()

# Configura a API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.warning("Configure a variável OPENAI_API_KEY no arquivo .env para começar.")
    st.stop()

client = OpenAI(api_key=api_key)

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


def processar_pergunta(pergunta):
    """Processa uma pergunta: gera SQL, executa e retorna resposta."""
    st.session_state.messages.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            schema = get_schema()

            historico = ""
            for msg in st.session_state.messages[:-1]:
                if msg["role"] == "user":
                    historico += f"Usuário: {msg['content']}\n"
                elif msg["role"] == "assistant":
                    historico += f"Assistente: {msg['content']}\n"

            contexto_historico = ""
            if historico:
                contexto_historico = f"""Histórico da conversa (use como contexto para entender referências como "ele", "ela", "isso", "o mesmo", etc.):
{historico}
"""

            prompt_sql = f"""Você é um assistente que converte perguntas em SQL.
Dado o esquema:
{schema}

{contexto_historico}Pergunta atual: {pergunta}
Retorne APENAS o código SQL, sem markdown, sem explicação."""

            try:
                response_sql = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt_sql}],
                )
                sql = response_sql.choices[0].message.content.strip()
                sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()

                df = execute_query(sql)
                resultado = df.to_string(index=False) if not df.empty else "Nenhum resultado encontrado."

                prompt_resposta = f"""{contexto_historico}Dado a pergunta atual: {pergunta}
E o resultado da consulta SQL: {resultado}
Forneça uma resposta natural e clara em português. Considere o histórico da conversa para dar uma resposta contextualizada."""

                response_nl = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt_resposta}],
                )
                resposta = response_nl.choices[0].message.content.strip()

                st.markdown(resposta)
                with st.expander("🔍 SQL executado"):
                    st.code(sql, language="sql")
                if not df.empty:
                    with st.expander("📊 Dados retornados"):
                        st.dataframe(df)

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

# Input fixo no rodapé com microfone ao lado
with st._bottom:
    col_mic, col_input = st.columns([0.07, 0.93], vertical_alignment="bottom")

    with col_mic:
        audio_bytes = audio_recorder(
            text="",
            recording_color="#e74c3c",
            neutral_color="#6c757d",
            icon_size="lg",
            pause_threshold=2.0,
            key="audio_recorder",
        )

    with col_input:
        pergunta = st.chat_input("Faça uma pergunta sobre o banco de dados...")

# Transcreve áudio
if audio_bytes:
    audio_hash = hash(audio_bytes)
    if st.session_state.get("last_audio_hash") != audio_hash:
        st.session_state.last_audio_hash = audio_hash
        recognizer = sr.Recognizer()
        audio_file = sr.AudioFile(io.BytesIO(audio_bytes))
        with audio_file as source:
            audio_data = recognizer.record(source)
        try:
            texto = recognizer.recognize_google(audio_data, language="pt-BR")
            st.session_state.audio_pendente = texto
            st.rerun()
        except sr.UnknownValueError:
            st.warning("Não foi possível entender o áudio.")

# Processa texto digitado ou áudio transcrito
if pergunta:
    processar_pergunta(pergunta)
elif "audio_pendente" in st.session_state:
    processar_pergunta(st.session_state.pop("audio_pendente"))
