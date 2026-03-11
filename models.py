from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, DateTime, Float, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from pgvector.sqlalchemy import Vector
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    role = Column(String(20), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    so_hieu = Column(String(100), unique=True, nullable=False)
    ten = Column(Text, nullable=False)
    loai = Column(String(30), nullable=False)
    co_quan = Column(String(200))
    ngay_ban_hanh = Column(Date)
    hieu_luc_tu = Column(Date)
    het_hieu_luc_tu = Column(Date)
    tinh_trang = Column(String(100))
    thay_the_boi = Column(String(100))
    sua_doi_boi = Column(Text)  # JSON string of so_hieu array
    sac_thue = Column(ARRAY(String(20)))
    category = Column(ARRAY(Text))
    tom_tat = Column(Text)
    noi_dung = Column(Text)
    link_tvpl = Column(Text)
    link_vbpl = Column(Text)
    tu_khoa = Column(ARRAY(Text))
    luu_y = Column(Text)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CongVan(Base):
    __tablename__ = "cong_van"

    id = Column(Integer, primary_key=True, autoincrement=True)
    so_hieu = Column(String(100), unique=True, nullable=False)
    ten = Column(Text)
    co_quan = Column(String(200))
    nguoi_nhan = Column(Text)
    ngay_ban_hanh = Column(Date)
    sac_thue = Column(ARRAY(String(20)))
    van_ban_trich_dan = Column(JSONB)
    ket_luan = Column(Text)
    noi_dung_day_du = Column(Text)
    tags = Column(ARRAY(Text))
    link_tvpl = Column(Text)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow)


class LegalIssue(Base):
    __tablename__ = "legal_issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    sac_thue = Column(ARRAY(String(20)))
    tags = Column(ARRAY(Text))
    embedding = Column(Vector(1536))
    created_at = Column(DateTime, default=datetime.utcnow)


class IssueRef(Base):
    __tablename__ = "issue_refs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issue_id = Column(Integer, ForeignKey("legal_issues.id"))
    ref_type = Column(String(20))
    ref_id = Column(Integer)
    relevance_score = Column(Float)
    note = Column(Text)


# Full-text search indexes created via raw SQL in init_db
