import re
import secrets
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from backend.models import (
    User, Rule, AuditLog, CommandRequest, RuleCreate, UserCreate,
    get_session, create_db_and_seeds
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_seeds()
    yield

app = FastAPI(lifespan=lifespan)

# --- AUTH ---
def get_current_user(x_api_key: str = Header(..., alias="X-API-Key"), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.api_key == x_api_key)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user

# --- MEMBER ENDPOINTS ---

@app.post("/api/commands")
def execute_command(
    req: CommandRequest, 
    user: User = Depends(get_current_user), 
    session: Session = Depends(get_session)
):
    if not req.command_text.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty")

    if user.credits <= 0:
        return {"status": "rejected", "message": "Insufficient credits", "new_balance": user.credits}

    rules = session.exec(select(Rule)).all()
    matched_action = "AUTO_REJECT" 
    match_found = False

    for rule in rules:
        try:
            if re.search(rule.pattern, req.command_text):
                matched_action = rule.action
                match_found = True
                break
        except re.error:
            continue

    if not match_found:
        matched_action = "AUTO_REJECT"

    try:
        if matched_action == "AUTO_ACCEPT":
            user.credits -= 1
            session.add(user)
            audit = AuditLog(user_id=user.id, command_text=req.command_text, action_taken="executed")
            session.add(audit)
            session.commit()
            session.refresh(user)
            return {"status": "executed", "new_balance": user.credits, "message": "Command executed"}
        else:
            audit = AuditLog(user_id=user.id, command_text=req.command_text, action_taken="rejected")
            session.add(audit)
            session.commit()
            return {"status": "rejected", "new_balance": user.credits, "message": "Blocked by rule"}
    except Exception as e:
        session.rollback()
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Transaction failed")

@app.get("/api/me")
def get_my_info(user: User = Depends(get_current_user)):
    return user

@app.get("/api/history")
def get_my_history(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return session.exec(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.timestamp.desc())).all()

# --- ADMIN ENDPOINTS ---

@app.get("/api/admin/rules")
def get_rules(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    return session.exec(select(Rule)).all()

@app.post("/api/admin/rules")
def add_rule(rule: RuleCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    if not rule.pattern.strip(): raise HTTPException(status_code=400, detail="Empty pattern")
    try:
        re.compile(rule.pattern)
    except re.error:
        raise HTTPException(status_code=400, detail="Invalid Regex")
    new_rule = Rule(pattern=rule.pattern, action=rule.action)
    session.add(new_rule)
    session.commit()
    return new_rule

# NEW: Delete Rule Endpoint
@app.delete("/api/admin/rules/{rule_id}")
def delete_rule(rule_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    session.delete(rule)
    session.commit()
    return {"ok": True}

@app.post("/api/admin/users")
def create_user(new_user: UserCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    # 1. Check Admin Permissions
    if user.role != "admin": 
        raise HTTPException(status_code=403, detail="Admin only")
    
    # 2. Check Valid Input
    if not new_user.username.strip(): 
        raise HTTPException(status_code=400, detail="Username required")
    
    # 3. CHECK FOR DUPLICATES (New Code)
    existing_user = session.exec(select(User).where(User.username == new_user.username)).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # 4. Create User
    api_key = secrets.token_urlsafe(16)
    db_user = User(username=new_user.username, role=new_user.role, api_key=api_key)
    
    session.add(db_user)
    session.commit()
    return {"username": db_user.username, "api_key": api_key}

@app.get("/api/admin/audit")
def get_all_audit(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    
    statement = select(AuditLog, User.username).join(User, AuditLog.user_id == User.id).order_by(AuditLog.timestamp.desc()).limit(200)
    results = session.exec(statement).all()
    
    return [{"id": l.id, "user": u, "command": l.command_text, "status": l.action_taken, "time": l.timestamp} for l, u in results]

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")