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
from sqlalchemy.dialects.postgresql import JSONB
from .models_base import Base


class Permit(Base):
    
  __tablename__ = 'permit'

  """
  Standard table.

  The root table for this database schema. Stores base analytical information about   
  a permit and the high-level details needed to link it to other records.

  Because ACCELA does not show us internal record PKs, we create our own. In practice 
  that means we have to save data related to addresses and contacts to their applicable 
  tables first, checking to see if they already exist and mapping them to their existing
  PK or creating a new one. Once we do that, we can insert the PK here for future 
  reference.

  For the other downstream records that just need to reference a permit, we can 
  immediately check/create the PK here and use that downstream.

  We will need to map the boolean fields in the 'property_detail' table to the 
  'work_type_description' field in this table. We will also eventually want to reconcile
  the default values for the various fields in this table with the default values in
  our JaxEPICS schema.
  """

  permit_pk = Column(BigInteger, primary_key=True, unique=True, index=True)  # Our auto-generated PK for links to other tables.
  total_cost_raw = Column(Numeric(1000, 2), nullable=True)  # From 'application_info.project_cost' or 'application_info.project_cost_includes_all_labor_materials'. ASSUMED TO BE: The amount charged to the client for work done.
  total_cost_clean = Column(Numeric(1000, 2), nullable=True, default=None)
  full_permit_number = Column(String(50), nullable=True)  # From 'permit.permit_number'. Format: "{year}-{city_abbreviation}-{permit_type_description_abbreviation}-{permit_primary_number}". City abbreviation for Missoula is "MSS".
  permit_primary_number = Column(String(255), nullable=True) # Drawn from 'permit.permit_number': Format: "#####".
  permit_sub_number = Column(Integer, nullable=True, default=None)
  permit_category = Column(String(255), nullable=True)  # TBD. Options: "Residential" or "Non-Residential".
  permit_type_description = Column(String(255), nullable=True)  # Drawn from 'permit.permit_type'. Options: "Building Commercial", "Building Residential", "Building Revision", "Demolition", "Electrical Permit", "Mechanical Permit", "Moving", "Building/Moving/NA/NA", "Plumbing Permit".
  status_description = Column(String(255), nullable=True)  # From 'application_info.status'. Options: "Approved", "Issued", "Open", "Withdrawn", "Final", "Expired", etc.
  proposed_use_description = Column(String(255), nullable=True)  # From 'permit.proposed_use'. This is an unstructured field.
  work_type_description = Column(String(255), nullable=True, default=None)  # Not yet mapped, we will eventually go through this using the boolean fields in our "property_detail" table.
  work_description = Column(Text, nullable=True)  # From 'permit.description'. Free-form text description.

  """ Dates related to the permit. """
  date_permit_requested = Column(DateTime, nullable=True)  # From 'processing.activated_date' WHERE 'processing.process_step' == "Application Intake" AND 'processing.status' == "Complete" AND 'processing.sub_step_type' == "Bold" AND 'processing.marked_status' == "Complete".
  date_permit_issued = Column(DateTime, nullable=True)  # From 'processing.marked_date' WHERE 'processing.process_step' == "Issue Permit" AND 'processing.status' == "Complete" AND 'processing.sub_step_type' == "Bold" AND 'processing.marked_status' == "Complete".
  date_permit_final = Column(DateTime, nullable=True)  # From 'application_info.end_date'.
  date_permit_expired = Column(DateTime, nullable=True)  # From 'application_info.permit_expiration_date'.
  date_work_started = Column(DateTime, nullable=True)  # From 'application_info.startdate' or 'application_info.start_date'. The date work started.
  date_work_expected = Column(DateTime, nullable=True)  # From 'application_info.targetdate'. The date they expect to finish work.
  date_work_completed = Column(DateTime, nullable=True)  # From 'application_info.completedate'. The date work was actually completed.
  is_completed = Column(Boolean, nullable=True, default=False)  # Mark to "True" WHERE 'processing.process_step' == "Complete" AND 'processing.status' == "Complete" AND 'processing.sub_step_type' == "Bold" AND 'processing.marked_status' == "Complete".  
  permit_url = Column(Text, nullable=True, default=None)  # From 'permit.permit_url'. To make it easier to revisit until the permit is marked as "is_completed".

  """ Individuals/companies/property related to the permit. """
  property_address_pk = Column(BigInteger, ForeignKey('property_address.property_address_pk'), nullable=True)
  property_owner_pk = Column(BigInteger, ForeignKey('contact.contact_pk'), nullable=True)
  contractor_company_pk = Column(BigInteger, ForeignKey('contact.contact_pk'), nullable=True)
  #contractor_primary_pk = Column(BigInteger, ForeignKey('contact.contact_pk'), nullable=True, default=None)
  #contractor_designer_pk = Column(BigInteger, ForeignKey('contact.contact_pk'), nullable=True, default=None)
  permit_company_id = Column(Integer, nullable=True, default=None)
  created_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
