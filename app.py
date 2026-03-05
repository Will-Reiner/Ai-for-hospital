import io
import os
from datetime import date

import plotly.graph_objects as go
import streamlit as st
import speech_recognition as sr
from audio_recorder_streamlit import audio_recorder
from openai import OpenAI
from dotenv import load_dotenv
from database import init_db, get_schema, execute_query, execute_query_raw

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

# Estado do chat
if "messages" not in st.session_state:
    st.session_state.messages = []


# --- Funções auxiliares para relatórios ---

def _formatar_brl(valor):
    """Formata float como moeda brasileira: R$ 1.234,56"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_data_br(data_iso):
    """Converte YYYY-MM-DD para DD/MM/AAAA."""
    if not data_iso:
        return ""
    try:
        parts = data_iso.split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except (IndexError, AttributeError):
        return str(data_iso)


def _gerar_agenda_hoje(medico_nome):
    """Gera relatório da agenda do médico para hoje."""
    hoje_str = date.today().isoformat()
    df = execute_query_raw("""
        SELECT c.hora_consulta, p.nome AS paciente, p.telefone, c.status, c.diagnostico
        FROM consultas c
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN medicos m ON c.medico_id = m.id
        WHERE m.nome = ? AND c.data_consulta = ?
        ORDER BY c.hora_consulta
    """, (medico_nome, hoje_str))

    if df.empty:
        return f"Nenhuma consulta encontrada para **{medico_nome}** hoje."

    hoje_br = _formatar_data_br(hoje_str)
    realizadas = len(df[df["status"] == "realizada"])
    agendadas = len(df[df["status"] == "agendada"])

    linhas = f"📋 **Agenda de {medico_nome} — {hoje_br}**\n\n"
    linhas += "| Horário | Paciente | Telefone | Status |\n"
    linhas += "|---------|----------|----------|--------|\n"
    for _, row in df.iterrows():
        linhas += f"| {row['hora_consulta']} | {row['paciente']} | {row['telefone']} | {row['status'].capitalize()} |\n"
    linhas += f"\n**Total: {len(df)} consultas** ({realizadas} realizadas, {agendadas} agendadas)"
    return linhas


def _gerar_resumo_ontem(medico_nome):
    """Gera resumo do dia anterior para o médico."""
    ontem_str = (date.today() - __import__('datetime').timedelta(days=1)).isoformat()
    df = execute_query_raw("""
        SELECT c.hora_consulta, p.nome AS paciente, c.diagnostico, c.status,
               COALESCE(pr.nome, '-') AS procedimento,
               COALESCE(co.valor_total, 0) AS valor
        FROM consultas c
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN medicos m ON c.medico_id = m.id
        LEFT JOIN contas co ON co.consulta_id = c.id
        LEFT JOIN procedimentos pr ON co.procedimento_id = pr.id
        WHERE m.nome = ? AND c.data_consulta = ?
        ORDER BY c.hora_consulta
    """, (medico_nome, ontem_str))

    if df.empty:
        return f"Nenhuma consulta encontrada para **{medico_nome}** ontem."

    ontem_br = _formatar_data_br(ontem_str)
    total_valor = df["valor"].sum()

    linhas = f"📊 **Resumo de {medico_nome} — {ontem_br}**\n\n"
    linhas += "| Horário | Paciente | Diagnóstico | Procedimento | Valor |\n"
    linhas += "|---------|----------|-------------|--------------|-------|\n"
    for _, row in df.iterrows():
        valor_fmt = f"R$ {row['valor']:.2f}" if row['valor'] > 0 else "-"
        diag = row['diagnostico'] or "-"
        linhas += f"| {row['hora_consulta']} | {row['paciente']} | {diag} | {row['procedimento']} | {valor_fmt} |\n"
    linhas += f"\n**Total de consultas: {len(df)}** | **Faturamento: R$ {total_valor:.2f}**"
    return linhas


def _gerar_dashboard_financeiro():
    """Gera dados para o dashboard financeiro do mês."""
    hoje = date.today()
    primeiro_dia = hoje.replace(day=1).isoformat()
    hoje_str = hoje.isoformat()

    # KPIs
    kpis = execute_query_raw("""
        SELECT
            COALESCE(SUM(valor_pago), 0) AS receita_total,
            COUNT(CASE WHEN status = 'pago' THEN 1 END) AS contas_pagas,
            COUNT(DISTINCT consulta_id) AS pacientes_atendidos,
            COALESCE(SUM(CASE WHEN status IN ('pendente','parcial') THEN valor_total - valor_pago ELSE 0 END), 0) AS valor_pendente
        FROM contas
        WHERE data_emissao BETWEEN ? AND ?
    """, (primeiro_dia, hoje_str))

    # Receita diária (últimos 30 dias)
    receita_diaria = execute_query_raw("""
        SELECT data_emissao AS data, SUM(valor_pago) AS receita
        FROM contas
        WHERE data_emissao >= date(?, '-30 days') AND valor_pago > 0
        GROUP BY data_emissao
        ORDER BY data_emissao
    """, (hoje_str,))

    # Receita por forma de pagamento
    receita_forma = execute_query_raw("""
        SELECT
            CASE forma_pagamento
                WHEN 'cartao_credito' THEN 'Cartão Crédito'
                WHEN 'cartao_debito' THEN 'Cartão Débito'
                WHEN 'pix' THEN 'PIX'
                WHEN 'dinheiro' THEN 'Dinheiro'
                WHEN 'convenio' THEN 'Convênio'
            END AS forma,
            SUM(valor) AS total
        FROM pagamentos
        WHERE data_pagamento BETWEEN ? AND ?
        GROUP BY forma_pagamento
    """, (primeiro_dia, hoje_str))

    # Receita por especialidade
    receita_esp = execute_query_raw("""
        SELECT m.especialidade, SUM(co.valor_pago) AS total
        FROM contas co
        JOIN consultas c ON co.consulta_id = c.id
        JOIN medicos m ON c.medico_id = m.id
        WHERE co.data_emissao BETWEEN ? AND ? AND co.valor_pago > 0
        GROUP BY m.especialidade
        ORDER BY total DESC
    """, (primeiro_dia, hoje_str))

    return {
        "kpis": kpis.iloc[0] if not kpis.empty else None,
        "receita_diaria": receita_diaria,
        "receita_forma": receita_forma,
        "receita_especialidade": receita_esp,
    }


def _gerar_html_dashboard(dados):
    """Gera arquivo HTML standalone com dashboard financeiro e retorna o conteúdo."""
    kpis = dados["kpis"]
    receita_total = _formatar_brl(float(kpis["receita_total"])) if kpis is not None else "R$ 0,00"
    contas_pagas = int(kpis["contas_pagas"]) if kpis is not None else 0
    pacientes = int(kpis["pacientes_atendidos"]) if kpis is not None else 0
    valor_pendente = _formatar_brl(float(kpis["valor_pendente"])) if kpis is not None else "R$ 0,00"

    hoje_br = date.today().strftime("%d/%m/%Y")

    # --- Gráfico 1: Receita Diária ---
    grafico_receita_diaria = ""
    rd = dados["receita_diaria"]
    if not rd.empty:
        rd_copy = rd.copy()
        rd_copy["data_br"] = rd_copy["data"].apply(_formatar_data_br)
        fig1 = go.Figure(go.Bar(x=rd_copy["data_br"], y=rd_copy["receita"],
                                marker_color="#4CAF50"))
        fig1.update_layout(title="Receita Diária (últimos 30 dias)",
                           xaxis_title="Data", yaxis_title="Receita (R$)",
                           xaxis_tickangle=-45, height=400,
                           template="plotly_white")
        grafico_receita_diaria = fig1.to_html(full_html=False, include_plotlyjs=False)

    # --- Gráfico 2: Receita por Forma de Pagamento ---
    grafico_forma_pgto = ""
    rf = dados["receita_forma"]
    if not rf.empty:
        fig2 = go.Figure(go.Pie(labels=rf["forma"], values=rf["total"],
                                marker=dict(colors=["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF"])))
        fig2.update_layout(title="Receita por Forma de Pagamento", height=400,
                           template="plotly_white")
        grafico_forma_pgto = fig2.to_html(full_html=False, include_plotlyjs=False)

    # --- Gráfico 3: Receita por Especialidade ---
    grafico_especialidade = ""
    re = dados["receita_especialidade"]
    if not re.empty:
        fig3 = go.Figure(go.Bar(x=re["total"], y=re["especialidade"],
                                orientation="h", marker_color="#36A2EB"))
        fig3.update_layout(title="Receita por Especialidade",
                           xaxis_title="Receita (R$)", yaxis_title="Especialidade",
                           height=400, template="plotly_white",
                           yaxis=dict(autorange="reversed"))
        grafico_especialidade = fig3.to_html(full_html=False, include_plotlyjs=False)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Financeiro — Hospital</title>
    <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0f2f5; color: #333; padding: 24px; }}
        h1 {{ text-align: center; margin-bottom: 8px; color: #1a1a2e; }}
        .subtitle {{ text-align: center; color: #666; margin-bottom: 32px; font-size: 1.1rem; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .kpi-card {{ background: #fff; border-radius: 12px; padding: 24px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .kpi-card .icon {{ font-size: 2rem; margin-bottom: 8px; }}
        .kpi-card .label {{ font-size: 0.9rem; color: #666; margin-bottom: 4px; }}
        .kpi-card .value {{ font-size: 1.8rem; font-weight: 700; color: #1a1a2e; }}
        .kpi-card.receita .value {{ color: #2e7d32; }}
        .kpi-card.pendente .value {{ color: #e65100; }}
        .chart-container {{ background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    </style>
</head>
<body>
    <h1>🏥 Dashboard Financeiro</h1>
    <p class="subtitle">Mês atual — gerado em {hoje_br}</p>

    <div class="kpi-grid">
        <div class="kpi-card receita">
            <div class="icon">💰</div>
            <div class="label">Receita Total</div>
            <div class="value">{receita_total}</div>
        </div>
        <div class="kpi-card">
            <div class="icon">✅</div>
            <div class="label">Contas Pagas</div>
            <div class="value">{contas_pagas}</div>
        </div>
        <div class="kpi-card">
            <div class="icon">👥</div>
            <div class="label">Pacientes Atendidos</div>
            <div class="value">{pacientes}</div>
        </div>
        <div class="kpi-card pendente">
            <div class="icon">⏳</div>
            <div class="label">Valor Pendente</div>
            <div class="value">{valor_pendente}</div>
        </div>
    </div>

    <div class="chart-container">{grafico_receita_diaria}</div>
    <div class="chart-container">{grafico_forma_pgto}</div>
    <div class="chart-container">{grafico_especialidade}</div>
</body>
</html>"""

    return html


def _gerar_pdf_completo(medico_nome):
    """Gera PDF A4 retrato com agenda de hoje, resumo de ontem e financeiro do mês."""
    from io import BytesIO
    import datetime as dt
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    hoje = date.today()
    ontem = hoje - dt.timedelta(days=1)
    hoje_str = hoje.isoformat()
    ontem_str = ontem.isoformat()
    hoje_br = hoje.strftime("%d/%m/%Y")
    ontem_br = ontem.strftime("%d/%m/%Y")
    primeiro_dia = hoje.replace(day=1).isoformat()

    import locale
    try:
        locale.setlocale(locale.LC_TIME, "pt_BR.UTF-8")
    except Exception:
        pass
    try:
        mes_nome = hoje.strftime("%B/%Y")
    except Exception:
        mes_nome = hoje.strftime("%m/%Y")

    buffer = BytesIO()
    W_PAGE, H_PAGE = A4
    MARGIN = 15 * mm
    W = W_PAGE - 2 * MARGIN

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=MARGIN,
        leftMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    s = getSampleStyleSheet()

    def _ps(name, **kwargs):
        base = kwargs.pop("parent", s["Normal"])
        return ParagraphStyle(name, parent=base, **kwargs)

    sT = _ps("sT", parent=s["Normal"], fontSize=18, fontName="Helvetica-Bold",
              textColor=colors.HexColor("#1a1a2e"), alignment=TA_CENTER, spaceAfter=2)
    sSub = _ps("sSub", fontSize=9, textColor=colors.HexColor("#666666"),
                alignment=TA_CENTER, spaceAfter=10)
    sSec = _ps("sSec", parent=s["Normal"], fontSize=12, fontName="Helvetica-Bold",
               textColor=colors.white, spaceBefore=12, spaceAfter=6)
    sMed = _ps("sMed", fontSize=9, textColor=colors.HexColor("#444444"), spaceAfter=6)
    sNorm = _ps("sNorm", fontSize=8, textColor=colors.HexColor("#333333"))
    sKL = _ps("sKL", fontSize=7, textColor=colors.HexColor("#666666"), alignment=TA_CENTER)
    sKV = _ps("sKV", fontSize=15, fontName="Helvetica-Bold",
               textColor=colors.HexColor("#1a1a2e"), alignment=TA_CENTER)
    sKVg = _ps("sKVg", fontSize=15, fontName="Helvetica-Bold",
                textColor=colors.HexColor("#2e7d32"), alignment=TA_CENTER)
    sKVo = _ps("sKVo", fontSize=15, fontName="Helvetica-Bold",
                textColor=colors.HexColor("#e65100"), alignment=TA_CENTER)
    sH3 = _ps("sH3", parent=s["Normal"], fontSize=10, fontName="Helvetica-Bold",
               textColor=colors.HexColor("#1a1a2e"), spaceBefore=6, spaceAfter=4)
    sFoot = _ps("sFoot", fontSize=7, textColor=colors.HexColor("#999999"), alignment=TA_CENTER)

    COR_AZUL = colors.HexColor("#1a1a2e")
    COR_VERDE = colors.HexColor("#2e7d32")
    COR_AZUL2 = colors.HexColor("#36A2EB")
    COR_VERDE2 = colors.HexColor("#4CAF50")
    COR_ROSA = colors.HexColor("#FF6384")
    COR_ROXO = colors.HexColor("#9966FF")
    COR_LISTRA = colors.HexColor("#f8f9fa")
    COR_BORDA = colors.HexColor("#dee2e6")
    COR_FUNDO_KPI = colors.HexColor("#f0f2f5")

    BASE_TABLE = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.4, COR_BORDA),
    ]

    def _header_style(cor):
        return [
            ("BACKGROUND", (0, 0), (-1, 0), cor),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COR_LISTRA]),
        ]

    def _section_bar(titulo, cor):
        """Retorna uma Table de uma célula que parece um cabeçalho colorido."""
        t = Table([[Paragraph(titulo, sSec)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cor),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return t

    def _kpi_table(labels, values, value_styles=None, n_cols=None):
        if n_cols is None:
            n_cols = len(labels)
        if value_styles is None:
            value_styles = [sKV] * n_cols
        row_l = [Paragraph(l, sKL) for l in labels]
        row_v = [Paragraph(v, value_styles[i]) for i, v in enumerate(values)]
        t = Table([row_l, row_v], colWidths=[W / n_cols] * n_cols)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COR_FUNDO_KPI),
            ("BACKGROUND", (0, 1), (-1, 1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWPADDING", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return t

    els = []

    # ── Cabeçalho ──────────────────────────────────────────────
    els.append(Paragraph("Relatorio Hospitalar Diario", sT))
    els.append(Paragraph(f"Gerado em {hoje_br}", sSub))
    els.append(HRFlowable(width="100%", thickness=2, color=COR_AZUL))
    els.append(Spacer(1, 5 * mm))

    # ══════════════════════════════════════════════════════
    # SECAO 1 — AGENDA DE HOJE
    # ══════════════════════════════════════════════════════
    els.append(_section_bar(f"AGENDA DE HOJE  —  {hoje_br}", COR_AZUL))
    els.append(Spacer(1, 2 * mm))
    els.append(Paragraph(f"Medico: {medico_nome}", sMed))

    df_ag = execute_query_raw("""
        SELECT c.hora_consulta, p.nome AS paciente, p.telefone, c.status, c.diagnostico
        FROM consultas c
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN medicos m ON c.medico_id = m.id
        WHERE m.nome = ? AND c.data_consulta = ?
        ORDER BY c.hora_consulta
    """, (medico_nome, hoje_str))

    if df_ag.empty:
        els.append(Paragraph(f"Nenhuma consulta para {medico_nome} hoje.", sNorm))
    else:
        real_ag = int((df_ag["status"] == "realizada").sum())
        agend_ag = int((df_ag["status"] == "agendada").sum())
        els.append(_kpi_table(
            ["Total de Consultas", "Realizadas", "Agendadas"],
            [str(len(df_ag)), str(real_ag), str(agend_ag)],
        ))
        els.append(Spacer(1, 3 * mm))

        rows_ag = [["Horario", "Paciente", "Telefone", "Status"]]
        for _, r in df_ag.iterrows():
            rows_ag.append([
                r["hora_consulta"],
                str(r["paciente"])[:28],
                r["telefone"] or "-",
                r["status"].capitalize(),
            ])
        t_ag = Table(rows_ag, colWidths=[W * 0.12, W * 0.40, W * 0.28, W * 0.20], repeatRows=1)
        t_ag.setStyle(TableStyle(BASE_TABLE + _header_style(COR_AZUL)))
        els.append(t_ag)

    els.append(Spacer(1, 5 * mm))

    # ══════════════════════════════════════════════════════
    # SECAO 2 — RESUMO DE ONTEM
    # ══════════════════════════════════════════════════════
    els.append(_section_bar(f"RESUMO DE ONTEM  —  {ontem_br}", colors.HexColor("#37474f")))
    els.append(Spacer(1, 2 * mm))
    els.append(Paragraph(f"Medico: {medico_nome}", sMed))

    df_on = execute_query_raw("""
        SELECT c.hora_consulta, p.nome AS paciente, c.diagnostico,
               COALESCE(pr.nome, '-') AS procedimento,
               COALESCE(co.valor_total, 0) AS valor_total,
               COALESCE(co.valor_pago, 0) AS valor_pago,
               COALESCE(co.status, '-') AS status_conta
        FROM consultas c
        JOIN pacientes p ON c.paciente_id = p.id
        JOIN medicos m ON c.medico_id = m.id
        LEFT JOIN contas co ON co.consulta_id = c.id
        LEFT JOIN procedimentos pr ON co.procedimento_id = pr.id
        WHERE m.nome = ? AND c.data_consulta = ?
        ORDER BY c.hora_consulta
    """, (medico_nome, ontem_str))

    if df_on.empty:
        els.append(Paragraph(f"Nenhuma consulta para {medico_nome} ontem.", sNorm))
    else:
        fat_on = float(df_on["valor_pago"].sum())
        tot_on = float(df_on["valor_total"].sum())
        areceber_on = tot_on - fat_on
        els.append(_kpi_table(
            ["Consultas", "Faturado", "A Receber"],
            [str(len(df_on)), _formatar_brl(fat_on), _formatar_brl(areceber_on)],
            value_styles=[sKV, sKVg, sKVo],
        ))
        els.append(Spacer(1, 3 * mm))

        rows_on = [["Horario", "Paciente", "Diagnostico", "Procedimento", "Valor"]]
        for _, r in df_on.iterrows():
            val = _formatar_brl(float(r["valor_pago"])) if r["valor_pago"] > 0 else "-"
            rows_on.append([
                r["hora_consulta"],
                str(r["paciente"])[:22],
                str(r["diagnostico"] or "-")[:24],
                str(r["procedimento"] or "-")[:20],
                val,
            ])
        t_on = Table(rows_on, colWidths=[W * 0.10, W * 0.24, W * 0.27, W * 0.24, W * 0.15], repeatRows=1)
        t_on.setStyle(TableStyle(BASE_TABLE + _header_style(colors.HexColor("#37474f"))))
        t_on.setStyle(TableStyle(BASE_TABLE + _header_style(colors.HexColor("#37474f")) + [
            ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ]))
        els.append(t_on)

    els.append(Spacer(1, 5 * mm))

    # ══════════════════════════════════════════════════════
    # SECAO 3 — FINANCEIRO DO MES
    # ══════════════════════════════════════════════════════
    els.append(_section_bar(f"FINANCEIRO DO MES  —  {mes_nome.upper()}", COR_VERDE))
    els.append(Spacer(1, 2 * mm))

    kpis_fin = execute_query_raw("""
        SELECT
            COALESCE(SUM(valor_pago), 0)            AS receita_total,
            COALESCE(SUM(valor_total), 0)           AS valor_bruto,
            COUNT(*)                                 AS total_contas,
            COUNT(CASE WHEN status='pago' THEN 1 END)     AS contas_pagas,
            COUNT(CASE WHEN status='pendente' THEN 1 END) AS contas_pend,
            COUNT(CASE WHEN status='parcial' THEN 1 END)  AS contas_parc,
            COUNT(DISTINCT consulta_id)              AS pacientes_atend,
            COALESCE(SUM(CASE WHEN status IN ('pendente','parcial')
                THEN valor_total - valor_pago ELSE 0 END), 0) AS valor_pendente
        FROM contas
        WHERE data_emissao BETWEEN ? AND ?
    """, (primeiro_dia, hoje_str))

    if not kpis_fin.empty:
        k = kpis_fin.iloc[0]
        rec = float(k["receita_total"])
        bruto = float(k["valor_bruto"])
        tot_c = int(k["total_contas"])
        pagas = int(k["contas_pagas"])
        pac = int(k["pacientes_atend"])
        pend = float(k["valor_pendente"])
        ticket = rec / pac if pac > 0 else 0.0
        taxa_adim = (pagas / tot_c * 100) if tot_c > 0 else 0.0
        media_dia = rec / hoje.day if hoje.day > 0 else 0.0
        desconto_total = bruto - rec

        # KPIs principais (2 colunas x 2 linhas)
        kpi2_data = [
            [Paragraph("Receita Total do Mes", sKL), Paragraph("Valor Pendente", sKL)],
            [Paragraph(_formatar_brl(rec), sKVg), Paragraph(_formatar_brl(pend), sKVo)],
            [Paragraph("Pacientes Atendidos", sKL), Paragraph("Contas Pagas", sKL)],
            [Paragraph(str(pac), sKV), Paragraph(str(pagas), sKV)],
        ]
        t_kpi2 = Table(kpi2_data, colWidths=[W / 2, W / 2])
        t_kpi2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COR_FUNDO_KPI),
            ("BACKGROUND", (0, 2), (-1, 2), COR_FUNDO_KPI),
            ("BACKGROUND", (0, 1), (-1, 1), colors.white),
            ("BACKGROUND", (0, 3), (-1, 3), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWPADDING", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        els.append(t_kpi2)
        els.append(Spacer(1, 3 * mm))

        # KPIs secundários (3 colunas)
        els.append(_kpi_table(
            ["Ticket Medio", "Taxa Adimplencia", "Media Diaria de Receita"],
            [_formatar_brl(ticket),
             f"{taxa_adim:.1f}%",
             _formatar_brl(media_dia)],
            value_styles=[sKV,
                          sKVg if taxa_adim >= 60 else sKVo,
                          sKV],
        ))
        els.append(Spacer(1, 3 * mm))

        # KPIs terciários
        els.append(_kpi_table(
            ["Total de Contas", "Contas Pendentes", "Desconto por Convenio"],
            [str(tot_c),
             str(int(k["contas_pend"])),
             _formatar_brl(desconto_total)],
            value_styles=[sKV,
                          sKVo if int(k["contas_pend"]) > 0 else sKV,
                          sKV],
        ))
        els.append(Spacer(1, 4 * mm))

    # -- Top Especialidades --
    els.append(Paragraph("Top Especialidades por Faturamento", sH3))
    df_esp = execute_query_raw("""
        SELECT m.especialidade,
               COUNT(DISTINCT co.consulta_id) AS consultas,
               SUM(co.valor_pago) AS total
        FROM contas co
        JOIN consultas c ON co.consulta_id = c.id
        JOIN medicos m ON c.medico_id = m.id
        WHERE co.data_emissao BETWEEN ? AND ? AND co.valor_pago > 0
        GROUP BY m.especialidade
        ORDER BY total DESC
        LIMIT 8
    """, (primeiro_dia, hoje_str))

    if not df_esp.empty:
        tot_esp = df_esp["total"].sum()
        rows_esp = [["Especialidade", "Consultas", "Faturamento", "% Total"]]
        for _, r in df_esp.iterrows():
            pct = float(r["total"]) / tot_esp * 100 if tot_esp > 0 else 0
            rows_esp.append([r["especialidade"], str(int(r["consultas"])),
                             _formatar_brl(float(r["total"])), f"{pct:.1f}%"])
        t_esp = Table(rows_esp, colWidths=[W * 0.44, W * 0.16, W * 0.25, W * 0.15], repeatRows=1)
        t_esp.setStyle(TableStyle(BASE_TABLE + _header_style(COR_AZUL2) + [
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ]))
        els.append(t_esp)
        els.append(Spacer(1, 4 * mm))

    # -- Top 5 Médicos --
    els.append(Paragraph("Top 5 Medicos por Faturamento", sH3))
    df_med = execute_query_raw("""
        SELECT m.nome, m.especialidade,
               COUNT(DISTINCT co.consulta_id) AS consultas,
               SUM(co.valor_pago) AS total
        FROM contas co
        JOIN consultas c ON co.consulta_id = c.id
        JOIN medicos m ON c.medico_id = m.id
        WHERE co.data_emissao BETWEEN ? AND ? AND co.valor_pago > 0
        GROUP BY m.nome, m.especialidade
        ORDER BY total DESC
        LIMIT 5
    """, (primeiro_dia, hoje_str))

    if not df_med.empty:
        rows_med = [["Medico", "Especialidade", "Qtd", "Faturamento"]]
        for _, r in df_med.iterrows():
            rows_med.append([str(r["nome"])[:28], r["especialidade"],
                             str(int(r["consultas"])), _formatar_brl(float(r["total"]))])
        t_med = Table(rows_med, colWidths=[W * 0.34, W * 0.31, W * 0.11, W * 0.24], repeatRows=1)
        t_med.setStyle(TableStyle(BASE_TABLE + _header_style(COR_VERDE2) + [
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ]))
        els.append(t_med)
        els.append(Spacer(1, 4 * mm))

    # -- Formas de Pagamento --
    els.append(Paragraph("Receita por Forma de Pagamento", sH3))
    df_fp = execute_query_raw("""
        SELECT
            CASE forma_pagamento
                WHEN 'cartao_credito' THEN 'Cartao Credito'
                WHEN 'cartao_debito'  THEN 'Cartao Debito'
                WHEN 'pix'            THEN 'PIX'
                WHEN 'dinheiro'       THEN 'Dinheiro'
                WHEN 'convenio'       THEN 'Convenio'
                ELSE forma_pagamento
            END AS forma,
            COUNT(*) AS qtd,
            SUM(valor) AS total
        FROM pagamentos
        WHERE data_pagamento BETWEEN ? AND ?
        GROUP BY forma_pagamento
        ORDER BY total DESC
    """, (primeiro_dia, hoje_str))

    if not df_fp.empty:
        tot_fp = df_fp["total"].sum()
        rows_fp = [["Forma de Pagamento", "Qtd", "Total", "% do Total"]]
        for _, r in df_fp.iterrows():
            pct = float(r["total"]) / tot_fp * 100 if tot_fp > 0 else 0
            rows_fp.append([r["forma"], str(int(r["qtd"])),
                            _formatar_brl(float(r["total"])), f"{pct:.1f}%"])
        t_fp = Table(rows_fp, colWidths=[W * 0.37, W * 0.13, W * 0.30, W * 0.20], repeatRows=1)
        t_fp.setStyle(TableStyle(BASE_TABLE + _header_style(COR_ROSA) + [
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ]))
        els.append(t_fp)
        els.append(Spacer(1, 4 * mm))

    # -- Convênios --
    els.append(Paragraph("Atendimentos por Convenio", sH3))
    df_conv = execute_query_raw("""
        SELECT COALESCE(cv.nome, 'Particular') AS convenio,
               COUNT(*) AS qtd,
               SUM(co.valor_pago) AS total
        FROM contas co
        JOIN consultas c ON co.consulta_id = c.id
        LEFT JOIN convenios cv ON co.convenio_id = cv.id
        WHERE co.data_emissao BETWEEN ? AND ?
        GROUP BY cv.nome
        ORDER BY total DESC
    """, (primeiro_dia, hoje_str))

    if not df_conv.empty:
        rows_conv = [["Convenio", "Atendimentos", "Total Recebido"]]
        for _, r in df_conv.iterrows():
            rows_conv.append([r["convenio"], str(int(r["qtd"])), _formatar_brl(float(r["total"]))])
        t_conv = Table(rows_conv, colWidths=[W * 0.44, W * 0.28, W * 0.28], repeatRows=1)
        t_conv.setStyle(TableStyle(BASE_TABLE + _header_style(COR_ROXO) + [
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ]))
        els.append(t_conv)

    # -- Diagnósticos mais frequentes no mês --
    els.append(Spacer(1, 4 * mm))
    els.append(Paragraph("Diagnosticos Mais Frequentes no Mes", sH3))
    df_diag = execute_query_raw("""
        SELECT c.diagnostico, COUNT(*) AS qtd
        FROM consultas c
        WHERE c.data_consulta BETWEEN ? AND ? AND c.diagnostico IS NOT NULL
        GROUP BY c.diagnostico
        ORDER BY qtd DESC
        LIMIT 8
    """, (primeiro_dia, hoje_str))

    if not df_diag.empty:
        rows_diag = [["Diagnostico", "Ocorrencias"]]
        for _, r in df_diag.iterrows():
            rows_diag.append([str(r["diagnostico"]), str(int(r["qtd"]))])
        t_diag = Table(rows_diag, colWidths=[W * 0.75, W * 0.25], repeatRows=1)
        t_diag.setStyle(TableStyle(BASE_TABLE + _header_style(colors.HexColor("#546e7a")) + [
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ]))
        els.append(t_diag)

    # ── Rodapé ─────────────────────────────────────────────
    els.append(Spacer(1, 8 * mm))
    els.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    els.append(Spacer(1, 2 * mm))
    els.append(Paragraph(
        f"Relatorio gerado automaticamente em {hoje_br} — Sistema Hospitalar",
        sFoot,
    ))

    doc.build(els)
    buffer.seek(0)
    return buffer.getvalue()


# --- Sidebar ---
with st.sidebar:
    st.header("📊 Consultas Rápidas")

    # Buscar lista de médicos
    try:
        df_medicos = execute_query_raw("SELECT id, nome FROM medicos ORDER BY nome")
        lista_medicos = df_medicos["nome"].tolist()
    except Exception:
        lista_medicos = []

    if lista_medicos:
        medico_selecionado = st.selectbox("Médico", lista_medicos, key="medico_select")

        if st.button("📄 Gerar Relatório PDF", use_container_width=True, type="primary"):
            st.session_state.acao_sidebar = ("gerar_pdf", medico_selecionado)

    st.divider()

    st.header("📋 Dados do Banco")
    if st.button("Ver dados de exemplo"):
        st.session_state.mostrar_dados = not st.session_state.get("mostrar_dados", False)

    if st.session_state.get("mostrar_dados", False):
        for tabela in ["pacientes", "medicos", "consultas", "convenios", "procedimentos", "contas", "pagamentos"]:
            st.subheader(tabela.capitalize())
            st.dataframe(execute_query(f"SELECT * FROM {tabela} LIMIT 20"), use_container_width=True)


# --- Processar ações do sidebar ---
if "acao_sidebar" in st.session_state:
    acao, param = st.session_state.pop("acao_sidebar")

    if acao == "gerar_pdf":
        with st.spinner("Gerando PDF..."):
            try:
                pdf_bytes = _gerar_pdf_completo(param)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"📄 **Relatório PDF gerado** para **{param}** — {date.today().strftime('%d/%m/%Y')}\n\nContém: Agenda de Hoje · Resumo de Ontem · Financeiro do Mês",
                    "type": "pdf_report",
                    "pdf_bytes": pdf_bytes,
                    "pdf_filename": f"relatorio_{date.today().isoformat()}.pdf",
                })
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")


def processar_pergunta(pergunta):
    """Processa uma pergunta: gera SQL, executa e retorna resposta."""
    st.session_state.messages.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            schema = get_schema()

            historico = ""
            mensagens_recentes = st.session_state.messages[-11:-1]
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
9. A coluna hora_consulta está no formato 'HH:MM' (ex: '08:00', '14:30').

VALORES CONHECIDOS:
- status de consultas: 'agendada', 'realizada'
- status de contas: 'pendente', 'pago', 'parcial'
- formas de pagamento: 'cartao_credito', 'cartao_debito', 'pix', 'dinheiro', 'convenio'
- categorias de procedimentos: 'consulta', 'exame', 'cirurgia', 'procedimento'
- tipos de convênio: 'particular', 'empresarial', 'individual'
- nomes de convênios: Unimed, Amil, SulAmérica, Bradesco Saúde, Hapvida, Particular
- especialidades: Cardiologia, Dermatologia, Ortopedia, Pediatria, Neurologia, Ginecologia, Oftalmologia, Psiquiatria, Urologia, Endocrinologia, Clínica Geral, Pneumologia, Gastroenterologia, Oncologia, Cirurgia Geral"""

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
                    "type": "ai",
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
        msg_type = msg.get("type", "ai")

        if msg_type == "financial" and "html_dashboard" in msg:
            st.markdown(msg["content"])
            st.download_button(
                label="📥 Baixar Dashboard HTML",
                data=msg["html_dashboard"],
                file_name="dashboard_financeiro.html",
                mime="text/html",
                key=f"dl_dashboard_{id(msg)}",
            )
        elif msg_type == "pdf_report" and "pdf_bytes" in msg:
            st.markdown(msg["content"])
            st.download_button(
                label="⬇️ Baixar Relatório PDF",
                data=msg["pdf_bytes"],
                file_name=msg.get("pdf_filename", "relatorio.pdf"),
                mime="application/pdf",
                key=f"dl_pdf_{id(msg)}",
            )
        else:
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
