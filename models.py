from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Reservoir(Base):
    __tablename__ = "reservoirs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    longitude = Column(Float, nullable=False)
    latitude = Column(Float, nullable=False)
    flood_limit_level = Column(Float, nullable=True)
    design_capacity = Column(Float, nullable=True)
    
    realtime_data = relationship("RealtimeData", back_populates="reservoir", cascade="all, delete-orphan")

class RealtimeData(Base):
    __tablename__ = "realtime_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reservoir_id = Column(Integer, ForeignKey("reservoirs.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    water_level = Column(Float, nullable=False)
    storage = Column(Float, nullable=False)
    
    reservoir = relationship("Reservoir", back_populates="realtime_data")