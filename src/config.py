from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TOKEN: str = 'DUMY_TOKEN'
    MONGO_INITDB_ROOT_USERNAME: str = 'root'
    MONGO_INITDB_ROOT_PASSWORD: str = 'example'
    MONGO_HOST: str = 'localhost'
    MONGO_PORT: str = '27017'

    class Config:
        env_file = '.env'


settings = Settings()
