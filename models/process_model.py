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

class PermitProcess(Base):
  __tablename__ = 'permit_process'

  """
  Custom table.

  Table that captures the process of intake, review, inspection, and completion of a
  permit. Unsure if we will keep this table long-term. But easy enough to grab so we do.

  All records should be overwritten with the latest information for a given permit when
  we go back to check permits that have not yet been marked as complete.

  A row should only be populated where we have a valid date in the 'date_activated' or
  'date_marked' columns. All other records should be ignored.
  """

  permit_process_pk = Column(BigInteger, primary_key=True, unique=True, index=True)
  permit_pk = Column(BigInteger, ForeignKey('permit.permit_pk'), nullable=False)

  process_status = Column(String(255), nullable=True)  # From 'processing.status'. Options: "Unkown", "Complete", "Active".
  process_step = Column(String(255), nullable=True)  # From 'processing.process_step'. Options: "Application Intake", "Issue Permit", "Complete", etc.
  process_type = Column(String(255), nullable=True)  # From 'processing.sub_step_type'. Options: "Complete", "Incomplete", "In Progress", etc.
  marked_status = Column(String(255), nullable=True)  # From 'processing.marked_status'. Options: "Complete", "Incomplete", "In Progress", etc.
  marked_by = Column(String(255), nullable=True)  # From 'processing.marked_by'. Name of the individual/user.
  marked_comment = Column(Text, nullable=True)  # From 'processing.comment'. Freeform text field.

  date_activated = Column(DateTime, nullable=True)  # From 'processing.activated_date'. The date the process was activated.
  date_marked = Column(DateTime, nullable=True)  # From 'processing.marked_date'. The date the process was marked as complete or incomplete.
  created_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)