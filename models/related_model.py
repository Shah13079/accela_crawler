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

class PermitRelated(Base):
  __tablename__ = 'permit_related'

  """
  Custom table.

  Tracks basic details related to other, linked permits. Can be used to link permits
  together for meta-level analysis of property development (at least, that is the goal).
  """
  permit_related_pk = Column(BigInteger, primary_key=True, autoincrement=True
    )
  permit_pk = Column(BigInteger, ForeignKey('permit.permit_pk'), nullable=False)
  full_permit_number = Column(String(255), nullable=True)  # From 'permit.permit_number'.
  related_permit_pk = Column(BigInteger, ForeignKey('permit.permit_pk'), nullable=True)  # Lookup for 'full_permit_number_2', only after all visits have been made, if we have data on that permit already.
  related_full_permit_number = Column(String(255), nullable=True)  # From 'permit.related_permit_number'. 

  """ Details pertaining to the second (i.e. related) permit. """
  related_permit_type = Column(String(255), nullable=True)  # From 'permit.permit_type'. Options: "Building Commercial", "Building Residential", "Building Revision", "Demolition", "Electrical Permit", "Mechanical Permit", "Moving", "Building/Moving/NA/NA", "Plumbing Permit".
  related_permit_description = Column(String(255), nullable=True)  # From 'permit.project_name'. The name of the project associated with the permit.
  related_permit_date = Column(DateTime, nullable=True)  # From 'permit.date'.
  related_permit_url = Column(Text, nullable=True, default=None)  # From 'permit.view_link'. To make it easier to revisit.  
  created_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)