import os
from dotenv import load_dotenv

load_dotenv()


def _get_secret(key: str, default=None):
    """Read local env first, then Streamlit secrets when deployed."""
    value = os.getenv(key)
    if value not in (None, ""):
        return value
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


DEEPSEEK_API_KEY = _get_secret("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"

MYSQL_CONFIG = {
    "host": _get_secret("MYSQL_HOST", "localhost"),
    "port": int(_get_secret("MYSQL_PORT", 3306)),
    "user": _get_secret("MYSQL_USER", "root"),
    "password": _get_secret("MYSQL_PASSWORD", ""),
    "database": _get_secret("MYSQL_DATABASE", "ai_fitness_coach"),
}
