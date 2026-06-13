from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String)
    delegated_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)

class Farm(Base):
    __tablename__ = "farms"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    location = Column(String)
    total_area_ha = Column(Float)
    parcels_count = Column(Integer, default=0)
    owner_id = Column(Integer, ForeignKey("users.id"))
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)

class Deadline(Base):
    __tablename__ = "deadlines"
    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"))
    competition_name = Column(String)
    deadline_date = Column(DateTime)
    status = Column(String, default="pending")

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    farm_id = Column(Integer, ForeignKey("farms.id"))
    competition_name = Column(String)
    submitted_date = Column(DateTime)
    status = Column(String, default="pending")
    signed = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

class Competition(Base):
    __tablename__ = "competitions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    deadline = Column(DateTime)
    active = Column(Boolean, default=True)