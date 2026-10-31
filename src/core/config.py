import os

def read_env(key: str) -> str:
    """Read a value directly from the .env file on disk (bypassing cached os.getenv)."""
    # Navigate up to the root directory where .env is located
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    if not os.path.exists(env_path):
        return os.getenv(key, "")
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return os.getenv(key, "")
