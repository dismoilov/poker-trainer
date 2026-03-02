from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # BackEnd/

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'app.db'}"

STRATEGIES_DIR = DATA_DIR / "strategies"
STRATEGIES_DIR.mkdir(exist_ok=True)

SPOTPACK_PATH = DATA_DIR / "spotpack.json"

# CORS origins (all localhost ports)
CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]
