import os

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError


def require_user() -> None:
    app_mode = os.getenv("APP_MODE", "production").strip().lower()
    if app_mode == "local":
        return
    if app_mode != "production":
        st.error("APP_MODE deve ser 'production' ou 'local'.")
        st.stop()

    try:
        auth_settings = st.secrets["auth"]
        allowed_email = st.secrets["app"]["allowed_email"].strip().casefold()
    except (StreamlitSecretNotFoundError, KeyError):
        st.title("Meu Controle")
        st.error("O acesso remoto ainda não foi configurado. Consulte o README.")
        st.stop()

    required_settings = (
        "redirect_uri",
        "cookie_secret",
        "client_id",
        "client_secret",
        "server_metadata_url",
    )
    if not allowed_email or any(not auth_settings.get(key) for key in required_settings):
        st.title("Meu Controle")
        st.error("A configuração de login está incompleta. Consulte o README.")
        st.stop()

    if not st.user.is_logged_in:
        st.title("Meu Controle")
        st.caption("Entre com sua conta Google para acessar seus lançamentos.")
        st.button("Entrar com Google", type="primary", on_click=st.login)
        st.stop()

    user_email = str(st.user.get("email", "")).strip().casefold()
    if not st.user.get("email_verified", False) or user_email != allowed_email:
        st.title("Meu Controle")
        st.error("Esta conta Google não está autorizada a acessar o aplicativo.")
        st.button("Sair", on_click=st.logout)
        st.stop()

    st.sidebar.caption("Conta conectada")
    st.sidebar.button("Sair", on_click=st.logout)