from sqlalchemy import Column, Integer, String
from pydantic import BaseModel
from db import Base
from db import engine

class UserTable(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(100), nullable=False)
    college = Column(String(50), nullable=True)
    interested_tags = Column(String(250), nullable=True)
    fcm_token = Column(String(255), nullable=True)  # FCM 토큰 저장
    device_type = Column(String(50), nullable=True)  # 디바이스 종류 (예: Android/iOS)