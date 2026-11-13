from datetime import date
from decimal import Decimal, InvalidOperation

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

def format_amount(value: float | Decimal) -> str:
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_amount(text: str) -> Decimal:
    value = text.strip().replace("R$", "").replace(" ", "")

    if not value:
        raise ValueError("Informe um valor.")

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")  # 1.234,56
        else:
            value = value.replace(",", "")  # 1,234.56
    else:
        value = value.replace(",", ".")  # 55,99 ou 55.99

    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Digite um valor válido, como 55,99.") from error

    if not amount.is_finite():
        raise ValueError("Digite um valor válido, como 55,99.")

    return amount


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
    initial_balance = store.get_initial_balance()
    with st.form("initial-balance-form"):
        starting_amount_text = st.text_input(
            "Valor que já tenho guardado",
            value=format_amount(
                initial_balance if initial_balance is not None else 0
            )
        )
        save_balance = st.form_submit_button("Salvar saldo inicial")
    if save_balance:
        try:
            starting_amount = parse_amount(starting_amount_text)
            if starting_amount < 0:
                raise ValueError("O saldo inicial não pode ser negativo.")
            store.set_initial_balance(float(starting_amount))
            st.success("Saldo inicial salvo.")
        except ValueError as error:
            st.error(str(error))
    with st.form("transaction-form", clear_on_submit=True):
        transaction_type = st.selectbox("Tipo", ["Despesa", "Receita"])
        transaction_date = st.date_input("Data", value=today, format="DD/MM/YYYY")
        category = st.selectbox("Categoria", CATEGORIES)
        amount_text = st.text_input(
            "Valor (R$)",
            placeholder="Ex.: 55,99",
        )
        description = st.text_input("Descrição", max_chars=120)
        submitted = st.form_submit_button(
            "Adicionar lançamento", type="primary", use_container_width=True
        )

    if submitted:
        try:
            parsed_amount = parse_amount(amount_text)
            if parsed_amount <= 0:
                raise ValueError("O valor precisa ser maior que zero.")

            store.add_transaction(
                transaction_date=transaction_date,
                transaction_type=transaction_type,
                category=category,
                description=description.strip(),
                amount=float(parsed_amount),
            )
            st.rerun()
        except ValueError as error:
            st.error(str(error))

    st.divider()
    backend_label = "Google Sheets" if store.is_cloud else "Este dispositivo (SQLite)"
    st.caption(f"Armazenamento: **{backend_label}**")

view = st.radio("Tela", ["Resumo", "Investimentos"], horizontal=True)
if view == "Investimentos":
    st.subheader("Investimentos")

    with st.form("investment-form", clear_on_submit=True):
        name = st.text_input("Nome do investimento")
        investment_type = st.selectbox(
            "Tipo", ["CDB", "Tesouro Direto", "Ação", "Fundo", "Outro"]
        )
        amount_invested_text = st.text_input(
            "Valor aplicado (R$)", placeholder="Ex.: 1.000,00"
        )
        current_value_text = st.text_input(
            "Valor atual (R$)", placeholder="Ex.: 1.055,90"
        )
        add_clicked = st.form_submit_button("Adicionar investimento")

    if add_clicked:
        try:
            parsed_invested = parse_amount(amount_invested_text)
            parsed_current = parse_amount(current_value_text)

            if not name.strip():
                raise ValueError("Informe o nome do investimento.")
            if parsed_invested <= 0:
                raise ValueError("O valor aplicado precisa ser maior que zero.")
            if parsed_current < 0:
                raise ValueError("O valor atual não pode ser negativo.")

            store.add_investment(
                name.strip(),
                investment_type,
                float(parsed_invested),
                float(parsed_current),
            )
            st.rerun()
        except ValueError as error:
            st.error(str(error))

    investments = store.list_investments()
    if investments.empty:
        st.info("Nenhum investimento cadastrado.")
    else:
        investments["Rendimento"] = (
            investments["current_value"] - investments["amount_invested"]
        )
        investments["Rendimento (%)"] = investments.apply(
            lambda row: (
                row["Rendimento"] / row["amount_invested"] * 100
                if row["amount_invested"] > 0 else 0
            ),
            axis=1,
        )
        st.dataframe(investments, hide_index=True, use_container_width=True)

        selected_id = st.selectbox(
            "Investimento para atualizar",
            investments["id"].tolist(),
            format_func=lambda value: investments.loc[
                investments["id"] == value, "name"
            ].iloc[0],
        )
        selected = investments.loc[investments["id"] == selected_id].iloc[0]
        with st.form("update-investment-form"):
            new_value_text = st.text_input(
                "Novo valor atual (R$)",
                value=format_amount(float(selected["current_value"])),
            )
            update_clicked = st.form_submit_button("Atualizar valor")
        if update_clicked:
            try:
                parsed_value = parse_amount(new_value_text)
                if parsed_value < 0:
                    raise ValueError("O valor atual não pode ser negativo.")

                store.update_investment_value(selected_id, float(parsed_value))
                st.rerun()
            except ValueError as error:
                st.error(str(error))

        investment_labels = {
            str(row["id"]): (
                f"{row['name']} | aplicado {money(float(row['amount_invested']))}"
            )
            for _, row in investments.iterrows()
        }
        with st.expander("Remover investimentos de teste"):
            selected_investment_ids = st.multiselect(
                "Selecione os investimentos para remover",
                options=list(investment_labels),
                format_func=investment_labels.get,
                key="investments-to-delete",
            )
            confirm_investment_delete = st.checkbox(
                "Confirmo a remoção dos investimentos selecionados",
                key="confirm-investment-delete",
            )
            if st.button(
                "Remover investimentos selecionados",
                disabled=not selected_investment_ids or not confirm_investment_delete,
                key="delete-investments-button",
            ):
                store.delete_investments(selected_investment_ids)
                st.rerun()

    st.stop()

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
total_income = float(
    transactions.loc[transactions["type"] == "Receita", "amount"].sum()
) if not transactions.empty else 0.0
total_expense = float(
    transactions.loc[transactions["type"] == "Despesa", "amount"].sum()
) if not transactions.empty else 0.0

initial_balance = store.get_initial_balance() or 0.0
available_balance = initial_balance + total_income - total_expense
month_result = income_total - expense_total

metric_income, metric_expense, metric_result, metric_balance = st.columns(4)
metric_income.metric("Ganhos no mês", money(income_total))
metric_expense.metric("Gastos no mês", money(expense_total))
metric_result.metric("Resultado do mês", money(month_result))
metric_balance.metric("Saldo disponível", money(available_balance))

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

with st.expander("Remover lançamentos de teste"):
    if transactions.empty:
        st.info("Não há lançamentos para remover.")
    else:
        transaction_labels = {
            str(row["id"]): (
                f"{pd.to_datetime(row['date']).strftime('%d/%m/%Y')} | "
                f"{row['type']} | {row['category']} | "
                f"{row['description'] or 'Sem descrição'} | "
                f"{money(float(row['amount']))}"
            )
            for _, row in transactions.iterrows()
        }
        selected_transaction_ids = st.multiselect(
            "Selecione os lançamentos para remover",
            options=list(transaction_labels),
            format_func=transaction_labels.get,
            key="transactions-to-delete",
        )
        confirm_transaction_delete = st.checkbox(
            "Confirmo a remoção dos lançamentos selecionados",
            key="confirm-transaction-delete",
        )
        if st.button(
            "Remover lançamentos selecionados",
            disabled=not selected_transaction_ids or not confirm_transaction_delete,
            key="delete-transactions-button",
        ):
            store.delete_transactions(selected_transaction_ids)
            st.rerun()