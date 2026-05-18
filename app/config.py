from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    debug: bool = False
    log_level: str = "INFO"

    masterbus_host: str = "178.128.149.217"
    masterbus_port: int = 3306
    masterbus_user: str = "antigravity"
    masterbus_pass: str = ""
    masterbus_db: str = "masterbus"

    class Config:
        env_file = ".env"


settings = Settings()
