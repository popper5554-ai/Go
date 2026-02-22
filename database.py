from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()

class Member(Base):
    __tablename__ = "members"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True) # Discord User ID
    username = Column(String)
    discriminator = Column(String)
    avatar = Column(String)
    access_token = Column(String)
    refresh_token = Column(String)
    expires_at = Column(DateTime)
    ip_address = Column(String)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

import os
from dotenv import load_dotenv
load_dotenv()

# Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vault.db")

# Fix for Neon/Heroku/Render using 'postgres://' instead of 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

from sqlalchemy import create_engine

# Engine configuration for different DB types
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Optimized for Neon.tech (Postgres)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        print("[OXY] Database Synced Successfully.")
    except Exception as e:
        print(f"[OXY] Database Sync Error: {e}")
