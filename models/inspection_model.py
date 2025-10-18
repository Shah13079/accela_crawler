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
from datetime import datetime
from .models_base import Base
from sqlalchemy.dialects.postgresql import JSONB


class PermitInspection(Base):

  __tablename__ = 'permit_inspection'

  """
  Standard table.

  At the top of the permit pop-up window, next to the 'title' element, there is a set of 
  parentheses with a number and some text in them, separated by a comma. Example: 
  "Rough Plumbing (1926826, Optional)". We should be grabbing these additional fields as 
  'permit_inspection_id' and 'is_required', respectively (where 'is_required' is a boolean 
  field that is 'True' by default and 'False' if the text is "Optional").
  """

  permit_inspection_id = Column(BigInteger, primary_key=True, unique=False, index=True)  # From 'TBD' source. If this field does not turn out to be unique, change this field to 'permit_inspection_pk' and add a new 'permit_inspection_pk' field as the primary key.
  permit_pk = Column(BigInteger, ForeignKey('permit.permit_pk'), nullable=False)

  """ Who conducted the inspection and what they found wrong (if anything). """
  default_inspector_username = Column(String(255), nullable=True, default=None)
  actual_inspector_name = Column(String(255), nullable=True)  # From 'inspections.result_by'. The name of the person who actually performed the inspection.
  actual_performed_by_name = Column(String(255), nullable=True, default=None)
  inspection_type_description = Column(String(255), nullable=True)  # From 'inspections.title'.
  discipline_type_description = Column(String(255), nullable=True, default=None)
  comments = Column(JSONB, nullable=True, default=dict)

  """ Boolean fields. """
  is_required = Column(Boolean, nullable=True)  # From 'TBD' source. "False" WHEN source == "Optional", "True" otherwise. 
  is_scheduled = Column(Boolean, nullable=True, default=True)  # By default, an inspection that shows up in ACCELA is scheduled.
  is_failed = Column(Boolean, nullable=True)  # From 'inspections.status'. "True" WHEN 'inspections.status' == "Fail", "False" otherwise. 
  is_passed = Column(Boolean, nullable=True)  # From 'inspections.status'. "True" WHEN 'inspections.status' == "Pass", "False" otherwise.
  is_completed = Column(Boolean, nullable=True)  # From 'inspections.status'. "True" WHEN 'inspections.status' IN ("Pass","Fail","Cancelled"), "False" otherwise.
  which_source = Column(String(255), nullable=True, default=None)

  """ Dates related to the inspection. """
  date_requested = Column(DateTime, nullable=True, default=None)
  date_started = Column(DateTime, nullable=True, default=None)
  date_completed = Column(DateTime, nullable=True)  # From 'inspections.date' and 'inspections.time'. WHEN 'inspections.status' IN ("Pass"), "NULL" otherwise.
  date_canceled = Column(DateTime, nullable=True)  # From 'inspections.date' and 'inspections.time'. WHEN 'inspections.status' IN ("Cancelled"), "NULL" otherwise.
  date_entered = Column(DateTime, nullable=True, default=None)
  date_updated = Column(DateTime, nullable=True)  # From 'inspections.date' and 'inspections.time'. 
  created_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)