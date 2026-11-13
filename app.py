from datetime import date

import pandas as pd
import streamlit as st
from streamlit_javascript import st_javascript

from auth import require_user
from storage import CATEGORIES, get_store


MONTHS_PT = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]

st.set_page_config(
    page_title="Meu Controle",
    page_icon="💸",
    layout="wide",
)

require_user()

st.markdown(
    """
    <style>
    :root {
        --ink: #173a35;
        --muted: #64736e;
        --paper: #f5f7f3;
        --line: #dce5dc;
        --green: #237a57;
        --mint: #e2f1e8;
        --coral: #c65e49;
    }
    .stApp { background: var(--paper); color: var(--ink); }
    [data-testid="stHeader"] { background: transparent; }
    h1, h2, h3 { color: var(--ink); }
    [data-testid="stMetric"] {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px 16px;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    div.stButton > button[kind="primary"] {
        background: var(--green);
        border-color: var(--green);
    }
    div.stButton > button[kind="primary"]:hover {
        background: #185f42;
        border-color: #185f42;
    }
    @media (max-width: 640px) {
        .block-container { padding: 1rem 1rem 2rem; }
        h1 { font-size: 1.8rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def browser_today() -> date:
    """Use the device's calendar date, falling back while the browser component loads."""
    browser_date = st_javascript(
        "(() => { const d = new Date(); "
        "return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), "
        "String(d.getDate()).padStart(2, '0')].join('-'); })()",
        key="device-local-date",
    )
    if isinstance(browser_date, str):
        try:
            return date.fromisoformat(browser_date)
        except ValueError:
            pass
    return date.today()


def money(value: float) -> str:
    formatted = f"R$ {value:,.2f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


store = get_store()
transactions = store.list_transactions()
today = browser_today()

st.title("Meu Controle")
st.caption("Receitas e despesas, organizadas sem complicação.")

current_month = today.strftime("%Y-%m")
available_months = sorted(
    set(transactions["date"].astype(str).str[:7]) if not transactions.empty else set(),
    reverse=True,
)
if current_month not in available_months:
    available_months.insert(0, current_month)

with st.sidebar:
    st.subheader("Novo lançamento")
    with st.form("transaction-form", clear_on_submit=True):
        transaction_type = st.selectbox("Tipo", ["Despesa", "Receita"])
        transaction_date = st.date_input("Data", value=today, format="DD/MM/YYYY")
        category = st.selectbox("Categoria", CATEGORIES)
        amount = st.number_input(
            "Valor (R$)", min_value=0.01, value=None, step=1.0, format="%.2f"
        )
        description = st.text_input("Descrição", max_chars=120)
        submitted = st.form_submit_button(
            "Adicionar lançamento", type="primary", use_container_width=True
        )

    if submitted:
        if amount is None or amount <= 0:
            st.error("Informe um valor maior que zero.")
        else:
            store.add_transaction(
                transaction_date=transaction_date,
                transaction_type=transaction_type,
                category=category,
                description=description.strip(),
                amount=float(amount),
            )
            st.success("Lançamento salvo.")
            st.rerun()

    st.divider()
    backend_label = "Google Sheets" if store.is_cloud else "Este dispositivo (SQLite)"
    st.caption(f"Armazenamento: **{backend_label}**")

st.subheader("Resumo do mês")
selected_month = st.selectbox(
    "Mês",
    available_months,
    format_func=lambda value: (
        f"{MONTHS_PT[pd.Period(value).month - 1].capitalize()} "
        f"{pd.Period(value).year}"
    ),
)

if transactions.empty:
    month_transactions = transactions
else:
    month_transactions = transactions[
        pd.to_datetime(transactions["date"]).dt.strftime("%Y-%m") == selected_month
    ].copy()

income_total = float(
    month_transactions.loc[month_transactions["type"] == "Receita", "amount"].sum()
) if not month_transactions.empty else 0.0
expense_total = float(
    month_transactions.loc[month_transactions["type"] == "Despesa", "amount"].sum()
) if not month_transactions.empty else 0.0
balance = income_total - expense_total

metric_income, metric_expense, metric_balance = st.columns(3)
metric_income.metric("Ganhos", money(income_total))
metric_expense.metric("Gastos", money(expense_total))
metric_balance.metric("Saldo", money(balance))

left, right = st.columns([1, 1.5], gap="large")
with left:
    st.subheader("Despesas por categoria")
    expense_categories = (
        month_transactions[month_transactions["type"] == "Despesa"]
        .groupby("category")["amount"]
        .sum()
        .sort_values(ascending=False)
    ) if not month_transactions.empty else pd.Series(dtype="float64")
    if expense_categories.empty:
        st.info("As despesas deste mês aparecerão aqui.")
    else:
        st.bar_chart(expense_categories, color="#237a57")

with right:
    st.subheader("Lançamentos")
    if month_transactions.empty:
        st.info("Nenhum lançamento neste mês. Use o formulário para adicionar o primeiro.")
    else:
        display_transactions = month_transactions.sort_values(
            ["date", "created_at"], ascending=False
        ).copy()
        display_transactions["date"] = pd.to_datetime(
            display_transactions["date"]
        ).dt.strftime("%d/%m/%Y")
        display_transactions["amount"] = display_transactions["amount"].map(money)
        display_transactions = display_transactions.rename(
            columns={
                "date": "Data",
                "type": "Tipo",
                "category": "Categoria",
                "description": "Descrição",
                "amount": "Valor",
            }
        )
        st.dataframe(
            display_transactions[["Data", "Tipo", "Categoria", "Descrição", "Valor"]],
            use_container_width=True,
            hide_index=True,
        )
        csv_data = month_transactions.drop(columns=["created_at"], errors="ignore").to_csv(
            index=False
        ).encode("utf-8-sig")
        st.download_button(
            "Baixar CSV do mês",
            data=csv_data,
            file_name=f"lancamentos-{selected_month}.csv",
            mime="text/csv",
        )