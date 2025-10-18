from sqlalchemy import Column, BigInteger, String, Text, Numeric
from .models_base import Base
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from sqlalchemy import (
  Column, 
  ForeignKey,
  BigInteger, 
  Integer, 
  Numeric, 
  String, 
  Text, 
  DateTime, 
  Boolean, 
)

class PermitCondition(Base):
  __tablename__ = 'permit_condition'

  """
  Custom table.

  This table is used to track conditions that are applied to a permit, such as 
  "Final Inspection Required" or "Zoning Compliance Permit Required". These 
  conditions are not necessarily tied to a specific inspection, but rather to the 
  permit as a whole.

  We will eventually go through this data in detail and determine if we need to keep
  all of it, don't need it, or if we want to join some of it elsewhere.
  """

  permit_condition_pk = Column(BigInteger, primary_key=True, unique=True, index=True)
  permit_pk = Column(BigInteger, ForeignKey('permit.permit_pk'), nullable=False)

  condition_group = Column(String(255), nullable=True)  # From 'conditions.condition_group_info'.
  condition_type = Column(String(50), nullable=True)  # From 'conditions.condition_type'.
  condition_type_code = Column(String(50), nullable=True)  # From 'conditions.condition_type_code'.
  condition_title = Column(String(255), nullable=True)  # From 'conditions.condition_title'.
  condition_description = Column(Text, nullable=True)  # From 'conditions.condition_description'.
  condition_status = Column(String(50), nullable=True)  # From 'conditions.condition_status'.
  date_updated = Column(DateTime, nullable=True)  # From 'conditions.condition_date'. 
  created_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)