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
from sqlalchemy.dialects.postgresql import JSONB
from .models_base import Base
from datetime import datetime

class PermitValuation(Base):
  __tablename__ = 'permit_valuation'

  """
  Custom table.

  This may have some overlap with the 'property_detail' table, specifically the
  "total_cost_job_valuation" field but we are keeping it separate for now. We may
  merge the two tables later if we find that the data is redundant.
  """
  valuation_pk = Column(BigInteger, primary_key=True, autoincrement=True )
  permit_pk = Column(BigInteger, ForeignKey('permit.permit_pk'), nullable=False)

  construction_type = Column(String(255), nullable=True)  # From 'valuation.type'. Type of construction/materials/systems affected.
  structure_type = Column(String(255), nullable=True)  # From 'valuation.occupancy'. Type of building affected.
  structure_size = Column(Integer, nullable=True)  # From 'valuation.quantity'. Size of the building affected.  
  structure_unit = Column(String(255), nullable=True)  # From 'valuation.unit'. How the size is measured: appears to be nearly 100% "SQFT".
  unit_cost_raw = Column(Numeric(1000, 2), nullable=True)  # From 'valuation.unit_cost'. The cost per unit of the work being done.
  job_value_raw = Column(Numeric(1000, 2), nullable=True)  # From 'valuation.job_value'. The total value of the work being done.
  created_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)