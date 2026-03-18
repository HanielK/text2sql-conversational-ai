import os
import psycopg
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(env_path, override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")


def get_connection():
    return psycopg.connect(
        DATABASE_URL,
        autocommit=True,
        prepare_threshold=None  # 🔥 THIS IS THE REAL FIX
    )