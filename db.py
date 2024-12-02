from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

user_name = "root"
user_pwd = "mysql123!"
db_host = "127.0.0.1"
db_port = "3306"
db_name = "my_caly_db"

DATABASE_URL = f"mysql+pymysql://{user_name}:{user_pwd}@{db_host}:{db_port}/{db_name}"

engine = create_engine(
    DATABASE_URL,
    echo=True
)

session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency
def get_db():
    db = session_local()
    try:
        yield db
    finally:
        db.close()
