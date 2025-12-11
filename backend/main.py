import re
import secrets
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from backend.models import (
    User, Rule, AuditLog, ApprovalRequest, CommandRequest, RuleCreate, UserCreate,
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

# --- MAIN COMMAND LOGIC ---

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

    # 1. Match Rules
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

    # 2. Handle Actions
    try:
        # --- NEW: REQUIRE_APPROVAL LOGIC ---
        if matched_action == "REQUIRE_APPROVAL":
            # Check if there is already an APPROVED request for this user + command
            # that hasn't been used yet.
            existing_approval = session.exec(
                select(ApprovalRequest)
                .where(ApprovalRequest.user_id == user.id)
                .where(ApprovalRequest.command_text == req.command_text)
                .where(ApprovalRequest.status == "APPROVED")
            ).first()

            if existing_approval:
                # It was approved! Consume the approval and execute.
                existing_approval.status = "USED"
                session.add(existing_approval)
                matched_action = "AUTO_ACCEPT" # Proceed to execution block below
            else:
                # No approval found. Create a pending request.
                # Check if pending already exists to avoid duplicates
                pending = session.exec(
                    select(ApprovalRequest)
                    .where(ApprovalRequest.user_id == user.id)
                    .where(ApprovalRequest.command_text == req.command_text)
                    .where(ApprovalRequest.status == "PENDING")
                ).first()
                
                if not pending:
                    new_req = ApprovalRequest(user_id=user.id, command_text=req.command_text)
                    session.add(new_req)
                    session.commit()
                
                # Log as "pending" in audit (optional, but good for visibility)
                audit = AuditLog(user_id=user.id, command_text=req.command_text, action_taken="pending_approval")
                session.add(audit)
                session.commit()
                
                return {"status": "pending", "message": "Approval required. Request sent to Admin.", "new_balance": user.credits}

        # --- EXECUTION LOGIC ---
        if matched_action == "AUTO_ACCEPT":
            user.credits -= 1
            session.add(user)
            audit = AuditLog(user_id=user.id, command_text=req.command_text, action_taken="executed")
            session.add(audit)
            session.commit()
            session.refresh(user)
            return {"status": "executed", "new_balance": user.credits, "message": "Command executed"}
        else:
            # AUTO_REJECT
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

@app.delete("/api/admin/rules/{rule_id}")
def delete_rule(rule_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    rule = session.get(Rule, rule_id)
    if rule:
        session.delete(rule)
        session.commit()
    return {"ok": True}

@app.post("/api/admin/users")
def create_user(new_user: UserCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    if not new_user.username.strip(): raise HTTPException(status_code=400, detail="Username required")
    
    # Check duplicate
    if session.exec(select(User).where(User.username == new_user.username)).first():
        raise HTTPException(status_code=400, detail="Username already exists")

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

# --- NEW: APPROVAL ENDPOINTS ---

@app.get("/api/admin/approvals")
def get_approvals(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    # Get all PENDING requests
    statement = select(ApprovalRequest, User.username).join(User, ApprovalRequest.user_id == User.id).where(ApprovalRequest.status == "PENDING").order_by(ApprovalRequest.timestamp.desc())
    results = session.exec(statement).all()
    return [{"id": r.id, "user": u, "command": r.command_text, "time": r.timestamp} for r, u in results]

@app.post("/api/admin/approvals/{req_id}/{action}")
def manage_approval(req_id: int, action: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role != "admin": raise HTTPException(status_code=403, detail="Admin only")
    if action not in ["approve", "reject"]: raise HTTPException(status_code=400, detail="Invalid action")
    
    req = session.get(ApprovalRequest, req_id)
    if not req: raise HTTPException(status_code=404, detail="Request not found")
    
    req.status = "APPROVED" if action == "approve" else "REJECTED"
    session.add(req)
    session.commit()
    return {"ok": True}

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")