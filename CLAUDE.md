# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Hospital database chatbot built with Streamlit + OpenAI GPT-4o-mini. Users query hospital data (patients, doctors, appointments) via natural language text or voice input in Portuguese (pt-BR). The app converts questions to SQL, executes against SQLite, then generates natural language responses.

## Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
pip install -r requirements.txt

# Run
streamlit run app.py

# Run in Dev Container
streamlit run app.py --server.enableCORS false --server.enableXsrfProtection false
```

App runs on `http://localhost:8501`. Requires `OPENAI_API_KEY` in `.env` file.

## Architecture

**Two-file application:**
- `app.py` — Streamlit UI + two-stage AI pipeline (question → SQL generation → query execution → natural language response)
- `database.py` — SQLite schema setup, sample data seeding, and query execution utilities

**Two-stage AI processing:**
1. GPT-4o-mini converts user question to a SELECT-only SQL query (destructive SQL is blocked)
2. Query results are fed back to GPT-4o-mini to generate a Portuguese natural language answer

**Database schema (SQLite, `hospital.db`):**
- `pacientes` — id, nome, data_nascimento, telefone, email
- `medicos` — id, nome, especialidade, crm
- `consultas` — id, paciente_id (FK), medico_id (FK), data_consulta, diagnostico, status

**State:** Managed via `st.session_state` (chat history, audio tracking). Last 10 messages kept as conversation context for pronoun/reference resolution.

## Key Conventions

- All UI text, prompts, and responses are in **Portuguese (pt-BR)**
- Dates formatted as DD/MM/AAAA (Brazilian standard)
- SQL generation prompt explicitly blocks INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, REPLACE
- Voice input uses Google Speech Recognition via `audio_recorder_streamlit`
