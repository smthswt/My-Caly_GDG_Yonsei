import json

from pydantic import BaseModel, validator
from typing import List, Optional

# 클라이언트가 서버로 데이터를 전송할 때 사용할 모델
class UserCreate(BaseModel):
    username: str
    password: str
    college: Optional[str] = None
    interested_tags: Optional[List[str]] = None
    # interested_tags: Optional[str] = None
    fcm_token: Optional[str] = None  # FCM 토큰 추가
    device_type: Optional[str] = None  # 디바이스 타입 (예: Android, iOS)

# 서버가 클라이언트로 데이터를 반환할 때 사용할 모델
class UserResponse(BaseModel):
    id: int
    username: str
    college: Optional[str] = None
    interested_tags: Optional[List[str]] = None
    # interested_tags: Optional[str] = None
    fcm_token: Optional[str] = None  # FCM 토큰 추가
    device_type: Optional[str] = None  # 디바이스 타입


    class Config:
        orm_mode = True  # SQLAlchemy 모델을 Pydantic 모델로 변환 가능하게 함

    # interested_tags를 JSON 문자열에서 List[str]로 변환
    @validator("interested_tags", pre=True)
    def parse_interested_tags(cls, value):
        if isinstance(value, str):  # JSON 문자열인 경우
            return json.loads(value)
        return value  # 이미 List[str]인 경우
