from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
from models import UserDB, TaskDB
from security import hash_password, verify_password
from auth import create_access_token, create_refresh_token, verify_token

Base.metadata.create_all(bind=engine)

app = FastAPI()
security = HTTPBearer()

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Schemas
class User(BaseModel):
    username: str
    password: str

class Task(BaseModel):
    title: str
    description: str = ""
    priority: str = "low"

class RefreshRequest(BaseModel):
    refresh_token: str

# Auth Middleware
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

# ---------------- AUTH ----------------

@app.post("/register")
def register(user: User, db: Session = Depends(get_db)):
    if db.query(UserDB).filter(UserDB.username == user.username).first():
        raise HTTPException(400, "User exists")

    new_user = UserDB(
        username=user.username,
        password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"msg": "User created"}

@app.post("/login")
def login(user: User, db: Session = Depends(get_db)):
    db_user = db.query(UserDB).filter(UserDB.username == user.username).first()

    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(401, "Invalid credentials")

    payload = {
        "user_id": db_user.id,
        "username": db_user.username,
        "role": db_user.role
    }

    return {
        "access_token": create_access_token(payload),
        "refresh_token": create_refresh_token(payload)
    }

@app.post("/refresh")
def refresh(req: RefreshRequest):
    payload = verify_token(req.refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")

    return {
        "access_token": create_access_token(payload)
    }

# ---------------- TASKS ----------------

@app.post("/tasks")
def create_task(task: Task, user=Depends(get_current_user), db: Session = Depends(get_db)):
    db_task = TaskDB(
        title=task.title,
        description=task.description,
        priority=task.priority,
        user_id=user["user_id"]
    )

    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    return db_task

@app.get("/tasks")
def get_tasks(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(TaskDB).filter(TaskDB.user_id == user["user_id"]).all()