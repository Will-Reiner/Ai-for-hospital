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

# CSS para alinhar o microfone ao campo de input
st.markdown("""
<style>
    /* Alinha o botão do microfone verticalmente ao centro do input */
    [data-testid="stBottom"] [data-testid="column"]:last-child {
        display: flex;
        align-items: center;
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

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
            mensagens_recentes = st.session_state.messages[-11:-1]  # últimas 10 mensagens
            for msg in mensagens_recentes:
                if msg["role"] == "user":
                    historico += f"Usuário: {msg['content']}\n"
                elif msg["role"] == "assistant":
                    historico += f"Assistente: {msg['content']}\n"

            contexto_historico = ""
            if historico:
                contexto_historico = f"""Histórico da conversa (use como contexto para entender referências como "ele", "ela", "isso", "o mesmo", etc.):
{historico}
"""

            sistema_sql = f"""Você é um assistente especializado em converter perguntas em consultas SQL para um banco de dados hospitalar SQLite.

ESQUEMA DO BANCO:
{schema}

REGRAS OBRIGATÓRIAS:
1. Gere APENAS consultas SELECT. NUNCA gere INSERT, UPDATE, DELETE, DROP, ALTER ou qualquer comando que modifique dados.
2. Retorne APENAS o código SQL puro, sem markdown, sem explicação, sem comentários.
3. Use JOINs quando a pergunta envolver dados de múltiplas tabelas (ex: nome do paciente + dados da consulta).
4. Para buscas por nome, use LIKE com '%' para busca parcial (ex: WHERE nome LIKE '%Ana%'). Use COLLATE NOCASE para ignorar maiúsculas/minúsculas.
5. Datas estão no formato 'YYYY-MM-DD'. Use date('now') para a data de hoje. Use strftime() para extrair mês/ano.
6. Use aliases claros para colunas de JOINs (ex: pacientes.nome AS paciente, medicos.nome AS medico).
7. Limite resultados a 50 linhas com LIMIT 50, a menos que a pergunta peça contagem ou agregação.
8. Para perguntas vagas ou impossíveis de responder com o esquema, retorne: SELECT 'Pergunta não pode ser respondida com os dados disponíveis' AS resposta

VALORES CONHECIDOS:
- status de consultas: 'agendada', 'realizada'
- especialidades: Cardiologia, Dermatologia, Ortopedia, Pediatria, Neurologia, Ginecologia, Oftalmologia, Psiquiatria, Urologia, Endocrinologia"""

            mensagem_usuario_sql = f"""{contexto_historico}Pergunta atual: {pergunta}"""

            try:
                response_sql = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": sistema_sql},
                        {"role": "user", "content": mensagem_usuario_sql},
                    ],
                )
                sql = response_sql.choices[0].message.content.strip()
                sql = sql.removeprefix("```sql").removeprefix("```").removesuffix("```").strip()

                # Validação de segurança: bloqueia comandos destrutivos
                sql_upper = sql.upper().strip()
                palavras_proibidas = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "REPLACE"]
                if any(sql_upper.startswith(p) for p in palavras_proibidas):
                    st.warning("A consulta gerada tentou modificar o banco de dados e foi bloqueada por segurança.")
                    st.session_state.messages.append({"role": "assistant", "content": "Desculpe, só posso realizar consultas de leitura no banco de dados."})
                    return

                df = execute_query(sql)
                resultado = df.to_string(index=False) if not df.empty else "Nenhum resultado encontrado."

                sistema_resposta = """Você é um assistente de um sistema hospitalar. Sua função é transformar resultados de consultas SQL em respostas naturais e claras em português brasileiro.

REGRAS:
1. Seja direto e objetivo. Não mencione SQL, banco de dados ou termos técnicos.
2. Quando houver múltiplos resultados, organize em lista ou formato estruturado.
3. Formate datas para o padrão brasileiro (DD/MM/AAAA).
4. Se o resultado for "Nenhum resultado encontrado", diga de forma amigável (ex: "Não encontrei registros para essa busca.").
5. Considere o histórico da conversa para entender referências como "ele", "ela", "o mesmo".
6. Não invente dados que não estejam no resultado. Responda apenas com base no que foi retornado."""

                mensagem_usuario_resposta = f"""{contexto_historico}Pergunta do usuário: {pergunta}
Resultado da consulta: {resultado}"""

                response_nl = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": sistema_resposta},
                        {"role": "user", "content": mensagem_usuario_resposta},
                    ],
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
    col_input, col_mic = st.columns([0.93, 0.07], vertical_alignment="center")

    with col_input:
        pergunta = st.chat_input("Faça uma pergunta sobre o banco de dados...")

    with col_mic:
        audio_bytes = audio_recorder(
            text="",
            recording_color="#e74c3c",
            neutral_color="#6c757d",
            icon_size="lg",
            pause_threshold=2.0,
            key="audio_recorder",
        )

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
