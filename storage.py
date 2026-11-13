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

INVESTMENT_HEADERS = [
    "id",
    "name",
    "type",
    "amount_invested",
    "current_value",
    "updated_at",
]

HEADERS = ["id", "date", "type", "category", "description", "amount", "created_at"]
CONFIG_HEADERS = ["key", "value"]

def open_worksheet(spreadsheet, title: str, headers: list[str]):
    import gspread

    try:
        worksheet = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=title, rows=1000, cols=len(headers)
        )

    if not worksheet.row_values(1):
        worksheet.append_row(headers)

    return worksheet


def read_worksheet_records(worksheet) -> list[dict[str, Any]]:
    from gspread.utils import ValueRenderOption

    return worksheet.get_all_records(
        value_render_option=ValueRenderOption.unformatted
    )


def delete_worksheet_rows(
    worksheet, records: list[dict[str, Any]], selected_ids: list[str]
) -> None:
    selected = {str(record_id) for record_id in selected_ids}
    rows = [
        row
        for row, record in enumerate(records, start=2)
        if str(record.get("id")) in selected
    ]
    if not rows:
        return

    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": worksheet.id,
                    "dimension": "ROWS",
                    "startIndex": row - 1,
                    "endIndex": row,
                }
            }
        }
        for row in sorted(rows, reverse=True)
    ]
    worksheet.spreadsheet.batch_update({"requests": requests})


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
            connection.execute(
                """CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value REAL NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS investments (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    amount_invested REAL NOT NULL,
                    current_value REAL NOT NULL,
                    updated_at TEXT NOT NULL
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

    def delete_transactions(self, transaction_ids: list[str]) -> None:
        with self._connect() as connection:
            connection.executemany(
                "DELETE FROM transactions WHERE id = ?",
                ((transaction_id,) for transaction_id in transaction_ids),
            )

    def get_initial_balance(self) -> float | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = 'initial_balance'"
            ).fetchone()
        return float(row[0]) if row else None

    def set_initial_balance(self, value: float) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO settings (key, value) VALUES ('initial_balance', ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (value,),
            )
    def delete_worksheet_rows(worksheet, records: list[dict[str, Any]], selected_ids: list[str]) -> None:
        selected = {str(record_id) for record_id in selected_ids}
        rows = [
            row
            for row, record in enumerate(records, start=2)
            if str(record.get("id")) in selected
        ]
        if not rows:
            return

        requests = [
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "ROWS",
                        "startIndex": row - 1,
                        "endIndex": row,
                    }
                }
            }
            for row in sorted(rows, reverse=True)
        ]
        worksheet.spreadsheet.batch_update({"requests": requests})


    def list_investments(self) -> pd.DataFrame:
        with self._connect() as connection:
            return pd.read_sql_query(
                "SELECT * FROM investments ORDER BY name", connection
            )

    def delete_investments(self, investment_ids: list[str]) -> None:
        with self._connect() as connection:
            connection.executemany(
                "DELETE FROM investments WHERE id = ?",
                ((investment_id,) for investment_id in investment_ids),
            )

    def add_investment(
        self, name: str, investment_type: str,
        amount_invested: float, current_value: float
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO investments
                   (id, name, type, amount_invested, current_value, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), name, investment_type, amount_invested,
                    current_value, datetime.now(timezone.utc).isoformat(),
                ),
            )

    def update_investment_value(
        self, investment_id: str, current_value: float
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE investments SET current_value = ?, updated_at = ?
                   WHERE id = ?""",
                (current_value, datetime.now(timezone.utc).isoformat(), investment_id),
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

        self.worksheet = open_worksheet(spreadsheet, worksheet_name, HEADERS)
        self.config_worksheet = open_worksheet(
            spreadsheet, "Config", CONFIG_HEADERS
        )
        self.investments_worksheet = open_worksheet(
            spreadsheet, "Investimentos", INVESTMENT_HEADERS
        )

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
            value_input_option="RAW",
        )

    def list_transactions(self) -> pd.DataFrame:
        records = read_worksheet_records(self.worksheet)
        if not records:
            return pd.DataFrame(columns=HEADERS)
        transactions = pd.DataFrame(records)
        transactions["amount"] = pd.to_numeric(transactions["amount"], errors="coerce").fillna(0)
        return transactions

    def delete_transactions(self, transaction_ids: list[str]) -> None:
        records = read_worksheet_records(self.worksheet)
        delete_worksheet_rows(self.worksheet, records, transaction_ids)

    def get_initial_balance(self) -> float | None:
        for record in read_worksheet_records(self.config_worksheet):
            if record.get("key") == "initial_balance":
                return float(record["value"])
        return None

    def set_initial_balance(self, value: float) -> None:
        records = read_worksheet_records(self.config_worksheet)
        for row, record in enumerate(records, start=2):
            if record.get("key") == "initial_balance":
                self.config_worksheet.update(
                    [[value]], range_name=f"B{row}", raw=True
                )
                return
        self.config_worksheet.append_row(
            ["initial_balance", value], value_input_option="RAW"
        )

    def list_investments(self) -> pd.DataFrame:
        records = read_worksheet_records(self.investments_worksheet)
        investments = pd.DataFrame(records, columns=INVESTMENT_HEADERS)
        for column in ("amount_invested", "current_value"):
            investments[column] = pd.to_numeric(
                investments[column], errors="coerce"
            ).fillna(0)
        return investments

    def delete_investments(self, investment_ids: list[str]) -> None:
        records = read_worksheet_records(self.investments_worksheet)
        delete_worksheet_rows(
            self.investments_worksheet, records, investment_ids
        )

    def add_investment(
        self, name: str, investment_type: str,
        amount_invested: float, current_value: float
    ) -> None:
        self.investments_worksheet.append_row([
            str(uuid.uuid4()), name, investment_type, amount_invested,
            current_value, datetime.now(timezone.utc).isoformat(),
        ], value_input_option="RAW")

    def update_investment_value(
        self, investment_id: str, current_value: float
    ) -> None:
        records = read_worksheet_records(self.investments_worksheet)
        for row, record in enumerate(records, start=2):
            if record.get("id") == investment_id:
                self.investments_worksheet.update(
                    [[current_value, datetime.now(timezone.utc).isoformat()]],
                    range_name=f"E{row}:F{row}",
                    raw=True,
                )
                return
        raise ValueError("Investimento não encontrado.")


@st.cache_resource
def get_store() -> SQLiteStore | GoogleSheetsStore:
    try:
        service_account = st.secrets["gcp_service_account"]
        sheets_config = st.secrets["google_sheets"]
    except StreamlitSecretNotFoundError:
        service_account = None
        sheets_config = None
    except (StreamlitSecretNotFoundError, KeyError):
        service_account = None
        sheets_config = None

    if service_account and sheets_config and sheets_config.get("spreadsheet_name"):
        return GoogleSheetsStore()

    if os.getenv("APP_MODE", "production").strip().lower() == "local":
        return SQLiteStore()

    st.error("Google Sheets não está configurado. Consulte o README.")
    st.stop()