import os
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


CATEGORIES = [
    "Alimentação",
    "Casa",
    "Contas",
    "Educação",
    "Lazer",
    "Saúde",
    "Salário",
    "Transporte",
    "Outros",
]
HEADERS = ["id", "date", "type", "category", "description", "amount", "created_at"]


class SQLiteStore:
    is_cloud = False

    def __init__(self) -> None:
        self.path = Path(os.getenv("EXPENSES_DB_PATH", ".data/finance.db"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('Receita', 'Despesa')),
                    category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL CHECK(amount > 0),
                    created_at TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def add_transaction(
        self,
        transaction_date: date,
        transaction_type: str,
        category: str,
        description: str,
        amount: float,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO transactions
                   (id, date, type, category, description, amount, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    transaction_date.isoformat(),
                    transaction_type,
                    category,
                    description,
                    amount,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def list_transactions(self) -> pd.DataFrame:
        with self._connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM transactions ORDER BY date DESC, created_at DESC",
                connection,
            )


class GoogleSheetsStore:
    is_cloud = True

    def __init__(self) -> None:
        import gspread

        service_account = dict(st.secrets["gcp_service_account"])
        self.client = gspread.service_account_from_dict(service_account)
        config = st.secrets["google_sheets"]
        spreadsheet = self.client.open(config["spreadsheet_name"])
        worksheet_name = config.get("worksheet_name", "Lancamentos")
        try:
            self.worksheet = spreadsheet.worksheet(worksheet_name)
        except gspread.WorksheetNotFound:
            self.worksheet = spreadsheet.add_worksheet(
                title=worksheet_name, rows=1000, cols=len(HEADERS)
            )
            self.worksheet.append_row(HEADERS)
        if not self.worksheet.row_values(1):
            self.worksheet.append_row(HEADERS)

    def add_transaction(
        self,
        transaction_date: date,
        transaction_type: str,
        category: str,
        description: str,
        amount: float,
    ) -> None:
        self.worksheet.append_row(
            [
                str(uuid.uuid4()),
                transaction_date.isoformat(),
                transaction_type,
                category,
                description,
                amount,
                datetime.now(timezone.utc).isoformat(),
            ],
            value_input_option="USER_ENTERED",
        )

    def list_transactions(self) -> pd.DataFrame:
        records: list[dict[str, Any]] = self.worksheet.get_all_records()
        if not records:
            return pd.DataFrame(columns=HEADERS)
        transactions = pd.DataFrame(records)
        transactions["amount"] = pd.to_numeric(transactions["amount"], errors="coerce").fillna(0)
        return transactions


@st.cache_resource
def get_store() -> SQLiteStore | GoogleSheetsStore:
    try:
        service_account = st.secrets["gcp_service_account"]
        sheets_config = st.secrets["google_sheets"]
    except StreamlitSecretNotFoundError:
        service_account = None
        sheets_config = None

    if service_account and sheets_config and sheets_config.get("spreadsheet_name"):
        return GoogleSheetsStore()

    if os.getenv("APP_MODE", "production").strip().lower() == "local":
        return SQLiteStore()

    st.error("Google Sheets não está configurado. Consulte o README.")
    st.stop()