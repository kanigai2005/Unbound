from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Session, create_engine, select

# --- CONFIGURATION ---
DATABASE_URL = "sqlite:///./gateway.db"
engine = create_engine(DATABASE_URL)

# --- DATABASE TABLES ---

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    api_key: str = Field(index=True, unique=True)
    role: str # "admin" or "member"
    credits: int = Field(default=100)

class Rule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pattern: str
    action: str # "AUTO_ACCEPT", "AUTO_REJECT", "REQUIRE_APPROVAL"

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    command_text: str
    action_taken: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# NEW: Approval Request Table
class ApprovalRequest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    command_text: str
    status: str = "PENDING" # PENDING, APPROVED, REJECTED, USED
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# --- API INPUT MODELS ---

class CommandRequest(SQLModel):
    command_text: str

class RuleCreate(SQLModel):
    pattern: str
    action: str 

class UserCreate(SQLModel):
    username: str
    role: str

# --- DB UTILITIES ---

def get_session():
    with Session(engine) as session:
        yield session

def create_db_and_seeds():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        if not session.exec(select(User).where(User.role == "admin")).first():
            print("--- SEEDING DATABASE ---")
            admin = User(username="admin", api_key="admin-secret-key", role="admin", credits=1000)
            session.add(admin)
            
            seeds = [
                # Critical commands now require approval
                Rule(pattern=r"sudo\s+", action="REQUIRE_APPROVAL"),
                Rule(pattern=r":\(\)\{ :\|:& \};:", action="AUTO_REJECT"),
                Rule(pattern=r"rm\s+-rf\s+/", action="AUTO_REJECT"),
                Rule(pattern=r"mkfs\.", action="AUTO_REJECT"),
                Rule(pattern=r"git\s+(status|log|diff)", action="AUTO_ACCEPT"),
                Rule(pattern=r"^(ls|cat|pwd|echo)", action="AUTO_ACCEPT"),
            ]
            for rule in seeds:
                session.add(rule)
            
            session.commit()
            print("Database seeded. Admin Key: admin-secret-key")