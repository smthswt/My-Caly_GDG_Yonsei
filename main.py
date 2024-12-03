import json

from fastapi import FastAPI, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from typing import List
from db import get_db
from model import UserTable
from schemas import UserCreate, UserResponse
from starlette.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
import requests
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials

app = FastAPI()

# rm -rf .venv
# python3 -m venv .venv  # 가상 환경 생성
# source .venv/bin/activate  # 가상 환경 활성화
# deactivate # 비활성화
# uvicorn main:app --reload # 서버 실행
# swagger UI - /docs || /redoc

# 비밀번호 해싱 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT 설정
SECRET_KEY = "your-secret-key"  # 환경 변수로 관리 권장
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# FCM 설정
FCM_SERVICE_ACCOUNT_KEY = "/key/my-caly-yonsei-firebase-adminsdk-3dz0d-41f1f65b74.json"
FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/my-caly-yonsei/messages:send"

# APScheduler
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_daily_notification, CronTrigger(hour=9, minute=0, timezone=timezone("Asia/Seoul")))
    scheduler.start()

@app.on_event("startup")
async def startup_event():
    start_scheduler()

# FCM API v1 푸시 알림 전송
def send_push_notification_v1(token: str, title: str, body: str):
    credentials = Credentials.from_service_account_file(
        FCM_SERVICE_ACCOUNT_KEY,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(Request())

    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": {
            "token": token,
            "notification": {
                "title": title,
                "body": body,
            },
        }
    }
    response = requests.post(FCM_ENDPOINT, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"FCM Error: {response.status_code}, {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.text)

    return {"message": "Notification sent successfully!"}

# 매일 오전 9시 푸시 알림 --> 이 부분 내용을 크롤링 날짜에 맞게 내용 보내면 되겠다.
def send_daily_notification():
    token = "CLIENT_FCM_TOKEN"  # 실제 토큰 가져오기 -> 데이터베이스에서 토큰값있는 회원만 보내기
    send_push_notification_v1(token, "Daily Reminder", "This is your daily notification.")

# OAuth2PasswordBearer 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 비밀번호 해싱 및 검증 함수
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# JWT 생성 함수
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# 현재 사용자 가져오기
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    username: str = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(UserTable).filter(UserTable.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/")
async def root():
    return "로그인/회원가입 서버"

# 회원 정보 전체 조회
@app.get("/users", response_model=List[UserResponse])
def read_users(db: Session = Depends(get_db)):
    users = db.query(UserTable).all()
    return users

# 회원 정보 조회
@app.get("/users/{username}", response_model=UserResponse)
def read_user(username: str, db: Session = Depends(get_db)):
    user = db.query(UserTable).filter(UserTable.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# 회원 정보 수정
@app.put("/users/{username}", response_model=UserResponse)
def update_user(username: str, user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(UserTable).filter(UserTable.username == username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db_user.username = user.username
    db_user.password = hash_password(user.password)  # 비밀번호 해싱
    db.commit()
    db.refresh(db_user)
    return db_user

# 회원 삭제
@app.delete("/users/{username}")
def delete_user(username: str, password: str, current_user: UserTable = Depends(get_current_user), db: Session = Depends(get_db)):
    # 본인 확인 (비밀번호 검증)
    if not verify_password(password, current_user.password):
        raise HTTPException(status_code=401, detail="Invalid password")

    # 관리자 권한 확인 (예: admin role이 있는 경우만 삭제 가능)
    if current_user.username != username and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")

    # 사용자 삭제
    db_user = db.query(UserTable).filter(UserTable.username == username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(db_user)
    db.commit()
    return {"detail": "User deleted"}

# 보호된 엔드포인트 -> 권한 계정 개발 시 필요
@app.get("/protected-route")
def protected_route(current_user: UserTable = Depends(get_current_user)):
    return {"message": f"Hello, {current_user.username}"}


# Query 관련 엔드포인트를 그룹화
user_query_router = APIRouter(prefix="/api/users", tags=["User query"])

# 회원 생성 - 회원가입
@user_query_router.post("/signup", response_model=UserResponse)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    hashed_password = hash_password(user.password)  # 비밀번호 해싱
    db_user = UserTable(username=user.username, password=hashed_password, college=None, interested_tags=None,)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 로그인 API
@user_query_router.post("/login")
def login(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(UserTable).filter(UserTable.username == username).first()
    if not user or not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# 단과대 및 관심_tags 조회
@user_query_router.get("/{username}/details", response_model=UserResponse)
def read_user_details(username: str, db: Session = Depends(get_db)):
    user = db.query(UserTable).filter(UserTable.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# 단과대 및 관심_tags 추가/수정 -> 둘 다/개별 다 가능, None일 경우 추가, 이미 값이 있을 경우 수정
@user_query_router.put("/{username}/details", response_model=UserResponse)
def update_user_details(
    username: str,
    college: Optional[str] = None,
    interested_tags: Optional[List[str]] = None,  # List[str]로 입력 받음
    db: Session = Depends(get_db),
):
    # 사용자 조회
    user = db.query(UserTable).filter(UserTable.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 값 추가/수정
    if college is not None:
        user.college = college

    if interested_tags is not None:
        # List[str] -> JSON 문자열 변환
        user.interested_tags = json.dumps(interested_tags)

    db.commit()
    db.refresh(user)
    return user

# Router를 앱에 포함
app.include_router(user_query_router)

# Query 관련 엔드포인트를 그룹화
notification_query_router = APIRouter(prefix="/api/notification", tags=["Push_Notification"])

# 클라이언트로 푸쉬 알림 보내기
@notification_query_router.post("/test/send_notification/")
async def send_notification(token: str, title: str, body: str):
    return send_push_notification_v1(token, title, body)

# 클라이언트에서 생성한 토큰 및 device type 정보 저장, 알림 권한 동의시 토큰 생성하는걸로? 어느 타이밍에 추가하는게 좋으려나, 일단 회원가입이랑 분리하는게 좋다함. 유연성.
@notification_query_router.put("/register_token")
def update_fcm_token(username: str, fcm_token: str, device_type: Optional[str] = None, db: Session = Depends(get_db)):
    user = db.query(UserTable).filter(UserTable.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.fcm_token = fcm_token
    user.device_type = device_type
    db.commit()
    return {"message": "FCM token updated successfully"}

# Router를 앱에 포함
app.include_router(notification_query_router)