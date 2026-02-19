import sqlite3
import pandas as pd
from datetime import date

DB_PATH = "hospital.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data_nascimento TEXT NOT NULL,
            telefone TEXT,
            email TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            especialidade TEXT NOT NULL,
            crm TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS consultas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER NOT NULL,
            medico_id INTEGER NOT NULL,
            data_consulta TEXT NOT NULL,
            diagnostico TEXT,
            status TEXT NOT NULL DEFAULT 'agendada',
            FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
            FOREIGN KEY (medico_id) REFERENCES medicos(id)
        )
    """)

    # Popula apenas se as tabelas estiverem vazias
    cursor.execute("SELECT COUNT(*) FROM pacientes")
    if cursor.fetchone()[0] == 0:
        hoje = date.today().isoformat()

        pacientes = [
            ("Ana Silva", "1985-03-12", "(11) 99876-5432", "ana.silva@email.com"),
            ("Carlos Oliveira", "1990-07-25", "(21) 98765-4321", "carlos.oliveira@email.com"),
            ("Maria Santos", "1978-11-08", "(31) 97654-3210", "maria.santos@email.com"),
            ("João Pereira", "1995-01-30", "(41) 96543-2109", "joao.pereira@email.com"),
            ("Fernanda Costa", "1988-06-17", "(51) 95432-1098", "fernanda.costa@email.com"),
            ("Rafael Souza", "1972-09-03", "(61) 94321-0987", "rafael.souza@email.com"),
            ("Juliana Lima", "2000-12-22", "(71) 93210-9876", "juliana.lima@email.com"),
            ("Pedro Almeida", "1983-04-14", "(81) 92109-8765", "pedro.almeida@email.com"),
            ("Camila Rodrigues", "1992-08-07", "(91) 91098-7654", "camila.rodrigues@email.com"),
            ("Lucas Ferreira", "1998-02-28", "(11) 90987-6543", "lucas.ferreira@email.com"),
        ]
        cursor.executemany(
            "INSERT INTO pacientes (nome, data_nascimento, telefone, email) VALUES (?, ?, ?, ?)",
            pacientes,
        )

        medicos = [
            ("Dr. Roberto Mendes", "Cardiologia", "CRM-SP 12345"),
            ("Dra. Patrícia Nunes", "Dermatologia", "CRM-RJ 23456"),
            ("Dr. André Barbosa", "Ortopedia", "CRM-MG 34567"),
            ("Dra. Beatriz Araújo", "Pediatria", "CRM-PR 45678"),
            ("Dr. Marcos Teixeira", "Neurologia", "CRM-RS 56789"),
            ("Dra. Renata Campos", "Ginecologia", "CRM-BA 67890"),
            ("Dr. Gustavo Ribeiro", "Oftalmologia", "CRM-DF 78901"),
            ("Dra. Larissa Martins", "Psiquiatria", "CRM-PE 89012"),
            ("Dr. Felipe Correia", "Urologia", "CRM-PA 90123"),
            ("Dra. Isabela Rocha", "Endocrinologia", "CRM-SP 01234"),
        ]
        cursor.executemany(
            "INSERT INTO medicos (nome, especialidade, crm) VALUES (?, ?, ?)",
            medicos,
        )

        consultas = [
            (1, 1, hoje, "Hipertensão leve", "realizada"),
            (2, 3, "2025-12-10", "Fratura no punho", "realizada"),
            (3, 2, "2026-01-15", "Dermatite de contato", "realizada"),
            (4, 4, hoje, "Resfriado comum", "realizada"),
            (5, 5, "2026-02-01", "Enxaqueca crônica", "realizada"),
            (6, 6, "2026-02-05", "Exame de rotina", "realizada"),
            (7, 7, "2026-02-10", "Miopia leve", "realizada"),
            (8, 8, hoje, "Ansiedade generalizada", "agendada"),
            (9, 9, "2026-02-20", "Consulta de rotina", "agendada"),
            (10, 10, "2026-02-25", "Hipotireoidismo", "agendada"),
        ]
        cursor.executemany(
            "INSERT INTO consultas (paciente_id, medico_id, data_consulta, diagnostico, status) VALUES (?, ?, ?, ?, ?)",
            consultas,
        )

    conn.commit()
    conn.close()


def get_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    schemas = [row[0] for row in cursor.fetchall() if row[0]]
    conn.close()
    return "\n\n".join(schemas)


def execute_query(sql):
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn)
        return df
    finally:
        conn.close()
