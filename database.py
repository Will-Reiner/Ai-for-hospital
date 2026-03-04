import sqlite3
import random
from datetime import date, timedelta

import pandas as pd

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
            hora_consulta TEXT,
            diagnostico TEXT,
            status TEXT NOT NULL DEFAULT 'agendada',
            FOREIGN KEY (paciente_id) REFERENCES pacientes(id),
            FOREIGN KEY (medico_id) REFERENCES medicos(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS convenios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            tipo TEXT NOT NULL,
            desconto_percentual REAL NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS procedimentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            preco REAL NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consulta_id INTEGER NOT NULL,
            procedimento_id INTEGER NOT NULL,
            convenio_id INTEGER,
            valor_total REAL NOT NULL,
            valor_pago REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pendente',
            data_emissao TEXT NOT NULL,
            data_pagamento TEXT,
            FOREIGN KEY (consulta_id) REFERENCES consultas(id),
            FOREIGN KEY (procedimento_id) REFERENCES procedimentos(id),
            FOREIGN KEY (convenio_id) REFERENCES convenios(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conta_id INTEGER NOT NULL,
            valor REAL NOT NULL,
            forma_pagamento TEXT NOT NULL,
            data_pagamento TEXT NOT NULL,
            FOREIGN KEY (conta_id) REFERENCES contas(id)
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM pacientes")
    if cursor.fetchone()[0] == 0:
        _seed_data(cursor)

    conn.commit()
    conn.close()


def _seed_data(cursor):
    random.seed(42)
    hoje = date.today()
    ontem = hoje - timedelta(days=1)

    # --- Pacientes (30) ---
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
        ("Beatriz Nascimento", "1987-05-19", "(11) 98111-2233", "beatriz.nascimento@email.com"),
        ("Thiago Monteiro", "1993-10-02", "(21) 97222-3344", "thiago.monteiro@email.com"),
        ("Larissa Duarte", "1980-01-15", "(31) 96333-4455", "larissa.duarte@email.com"),
        ("Gabriel Carvalho", "1975-08-22", "(41) 95444-5566", "gabriel.carvalho@email.com"),
        ("Isabela Moreira", "1999-04-07", "(51) 94555-6677", "isabela.moreira@email.com"),
        ("Diego Fernandes", "1982-12-30", "(61) 93666-7788", "diego.fernandes@email.com"),
        ("Natália Vieira", "1996-06-11", "(71) 92777-8899", "natalia.vieira@email.com"),
        ("Rodrigo Pinto", "1989-09-25", "(81) 91888-9900", "rodrigo.pinto@email.com"),
        ("Vanessa Gomes", "1977-03-08", "(91) 90999-0011", "vanessa.gomes@email.com"),
        ("Marcelo Dias", "2001-11-14", "(11) 98100-1122", "marcelo.dias@email.com"),
        ("Patrícia Freitas", "1986-07-03", "(21) 97200-2233", "patricia.freitas@email.com"),
        ("André Lopes", "1994-02-18", "(31) 96300-3344", "andre.lopes@email.com"),
        ("Carolina Barros", "1981-10-27", "(41) 95400-4455", "carolina.barros@email.com"),
        ("Felipe Cardoso", "1997-08-09", "(51) 94500-5566", "felipe.cardoso@email.com"),
        ("Renata Machado", "1984-04-21", "(61) 93600-6677", "renata.machado@email.com"),
        ("Bruno Teixeira", "1991-01-06", "(71) 92700-7788", "bruno.teixeira@email.com"),
        ("Aline Castro", "1979-06-29", "(81) 91800-8899", "aline.castro@email.com"),
        ("Vinícius Ramos", "2002-09-13", "(91) 90900-9900", "vinicius.ramos@email.com"),
        ("Daniela Cunha", "1988-12-05", "(11) 98000-0011", "daniela.cunha@email.com"),
        ("Eduardo Martins", "1976-05-17", "(21) 97100-1122", "eduardo.martins@email.com"),
    ]
    cursor.executemany(
        "INSERT INTO pacientes (nome, data_nascimento, telefone, email) VALUES (?, ?, ?, ?)",
        pacientes,
    )

    # --- Médicos (15) ---
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
        ("Dr. Ricardo Alves", "Clínica Geral", "CRM-SP 11234"),
        ("Dra. Fernanda Borges", "Pneumologia", "CRM-RJ 22345"),
        ("Dr. Paulo Henrique", "Gastroenterologia", "CRM-MG 33456"),
        ("Dra. Camila Farias", "Oncologia", "CRM-PR 44567"),
        ("Dr. Leonardo Costa", "Cirurgia Geral", "CRM-RS 55678"),
    ]
    cursor.executemany(
        "INSERT INTO medicos (nome, especialidade, crm) VALUES (?, ?, ?)",
        medicos,
    )

    # --- Convênios (6) ---
    convenios = [
        ("Unimed", "empresarial", 30.0),
        ("Amil", "empresarial", 25.0),
        ("SulAmérica", "individual", 20.0),
        ("Bradesco Saúde", "empresarial", 28.0),
        ("Hapvida", "individual", 15.0),
        ("Particular", "particular", 0.0),
    ]
    cursor.executemany(
        "INSERT INTO convenios (nome, tipo, desconto_percentual) VALUES (?, ?, ?)",
        convenios,
    )

    # --- Procedimentos (15) ---
    procedimentos = [
        ("Consulta Cardiologia", "consulta", 350.00),
        ("Consulta Dermatologia", "consulta", 300.00),
        ("Consulta Ortopedia", "consulta", 320.00),
        ("Consulta Pediatria", "consulta", 280.00),
        ("Consulta Neurologia", "consulta", 380.00),
        ("Consulta Ginecologia", "consulta", 300.00),
        ("Consulta Clínica Geral", "consulta", 250.00),
        ("Hemograma Completo", "exame", 80.00),
        ("Raio-X", "exame", 150.00),
        ("Ressonância Magnética", "exame", 850.00),
        ("Eletrocardiograma", "exame", 200.00),
        ("Ultrassonografia", "exame", 250.00),
        ("Biópsia", "procedimento", 600.00),
        ("Pequena Cirurgia", "cirurgia", 1500.00),
        ("Endoscopia", "procedimento", 450.00),
    ]
    cursor.executemany(
        "INSERT INTO procedimentos (nome, categoria, preco) VALUES (?, ?, ?)",
        procedimentos,
    )

    # --- Consultas (~120) espalhadas nos últimos 90 dias ---
    diagnosticos = [
        "Hipertensão leve", "Resfriado comum", "Dermatite de contato",
        "Fratura no punho", "Enxaqueca crônica", "Exame de rotina",
        "Miopia leve", "Ansiedade generalizada", "Consulta de rotina",
        "Hipotireoidismo", "Lombalgia", "Bronquite", "Gastrite",
        "Diabetes tipo 2", "Infecção urinária", "Rinite alérgica",
        "Tendinite", "Anemia", "Colesterol alto", "Dor torácica",
    ]
    horarios = [
        "08:00", "08:30", "09:00", "09:30", "10:00", "10:30",
        "11:00", "11:30", "13:00", "13:30", "14:00", "14:30",
        "15:00", "15:30", "16:00", "16:30", "17:00",
    ]

    consulta_id = 0

    # Consultas para hoje e ontem: cada médico tem 3-5 consultas
    for dia in [hoje, ontem]:
        dia_str = dia.isoformat()
        for medico_id in range(1, 16):
            n_consultas = random.randint(3, 5)
            horas_dia = random.sample(horarios, n_consultas)
            horas_dia.sort()
            for hora in horas_dia:
                paciente_id = random.randint(1, 30)
                diag = random.choice(diagnosticos)
                if dia == hoje:
                    status = random.choice(["agendada", "agendada", "realizada"])
                else:
                    status = "realizada"
                cursor.execute(
                    "INSERT INTO consultas (paciente_id, medico_id, data_consulta, hora_consulta, diagnostico, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (paciente_id, medico_id, dia_str, hora, diag, status),
                )
                consulta_id += 1

    # Consultas nos últimos 90 dias (excluindo hoje e ontem)
    for i in range(2, 90):
        dia = hoje - timedelta(days=i)
        dia_str = dia.isoformat()
        # 5-10 consultas por dia
        n_consultas = random.randint(5, 10)
        for _ in range(n_consultas):
            paciente_id = random.randint(1, 30)
            medico_id = random.randint(1, 15)
            hora = random.choice(horarios)
            diag = random.choice(diagnosticos)
            status = "realizada"
            cursor.execute(
                "INSERT INTO consultas (paciente_id, medico_id, data_consulta, hora_consulta, diagnostico, status) VALUES (?, ?, ?, ?, ?, ?)",
                (paciente_id, medico_id, dia_str, hora, diag, status),
            )
            consulta_id += 1

    # Buscar todas consultas realizadas para gerar contas
    cursor.execute("SELECT id, medico_id, data_consulta FROM consultas WHERE status = 'realizada'")
    consultas_realizadas = cursor.fetchall()

    # Mapear médico -> procedimento de consulta mais provável
    medico_procedimento = {
        1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7,
        8: 7, 9: 7, 10: 7, 11: 7, 12: 7, 13: 7, 14: 7, 15: 7,
    }

    # --- Contas e Pagamentos ---
    formas_pagamento = ["cartao_credito", "cartao_debito", "pix", "dinheiro", "convenio"]

    conta_id = 0
    for cons_id, medico_id, data_consulta in consultas_realizadas:
        # 80% das consultas realizadas geram conta
        if random.random() > 0.80:
            continue

        proc_id = medico_procedimento.get(medico_id, 7)
        # Às vezes adiciona exame extra
        if random.random() < 0.3:
            proc_id = random.randint(8, 15)

        # Buscar preço do procedimento
        cursor.execute("SELECT preco FROM procedimentos WHERE id = ?", (proc_id,))
        preco = cursor.fetchone()[0]

        # Convênio: 70% das consultas têm convênio
        convenio_id = None
        desconto = 0
        if random.random() < 0.70:
            convenio_id = random.randint(1, 5)  # excluir Particular (id=6)
            cursor.execute("SELECT desconto_percentual FROM convenios WHERE id = ?", (convenio_id,))
            desconto = cursor.fetchone()[0]

        valor_total = round(preco * (1 - desconto / 100), 2)

        # Status da conta
        r = random.random()
        if r < 0.65:
            status_conta = "pago"
            valor_pago = valor_total
            data_pagamento = data_consulta
        elif r < 0.85:
            status_conta = "parcial"
            valor_pago = round(valor_total * random.uniform(0.3, 0.7), 2)
            data_pagamento = data_consulta
        else:
            status_conta = "pendente"
            valor_pago = 0
            data_pagamento = None

        cursor.execute(
            "INSERT INTO contas (consulta_id, procedimento_id, convenio_id, valor_total, valor_pago, status, data_emissao, data_pagamento) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cons_id, proc_id, convenio_id, valor_total, valor_pago, status_conta, data_consulta, data_pagamento),
        )
        conta_id += 1
        current_conta_id = cursor.lastrowid

        # Gerar pagamentos para contas pagas ou parciais
        if status_conta in ("pago", "parcial"):
            forma = random.choice(formas_pagamento)
            if convenio_id and random.random() < 0.4:
                forma = "convenio"
            cursor.execute(
                "INSERT INTO pagamentos (conta_id, valor, forma_pagamento, data_pagamento) VALUES (?, ?, ?, ?)",
                (current_conta_id, valor_pago, forma, data_consulta),
            )


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

        # Renomeia colunas duplicadas para evitar erro no Streamlit / PyArrow
        new_cols = []
        col_counts = {}
        for col in df.columns:
            if col not in col_counts:
                col_counts[col] = 1
                new_cols.append(col)
            else:
                col_counts[col] += 1
                new_cols.append(f"{col}_{col_counts[col]}")
        df.columns = new_cols

        return df
    finally:
        conn.close()


def execute_query_raw(sql, params=None):
    """Executa query parametrizada e retorna DataFrame."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn, params=params)
        return df
    finally:
        conn.close()
