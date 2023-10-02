from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TOKEN: str = 'DUMY_TOKEN'

    class Config:
        env_file = '.env'


settings = Settings()
