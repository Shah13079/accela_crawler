from sqlalchemy import Column, BigInteger, String, Text, Numeric, DateTime
from .models_base import Base
from datetime import datetime

class PropertyAddress(Base):
    __tablename__ = 'property_address'
    
    property_address_pk = Column(BigInteger, primary_key=True, unique=True, index=True)
    parcel_id = Column(String(255), nullable=True)
    address_base = Column(String(255), nullable=True)
    address_full = Column(Text, nullable=True)
    street_number = Column(String(255), nullable=True, default=None)
    street_name = Column(String(255), nullable=True, default=None)
    street_type = Column(String(255), nullable=True, default=None)
    street_unit = Column(String(255), nullable=True, default=None)
    city = Column(String(255), nullable=True, default='Missoula')
    state = Column(String(255), nullable=True, default='MT')
    postal_code = Column(String(50), nullable=True, default=None)
    longitude = Column(Numeric(9, 6), nullable=True, default=None)
    latitude = Column(Numeric(9, 6), nullable=True, default=None)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)