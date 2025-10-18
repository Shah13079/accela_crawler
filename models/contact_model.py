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

class Contact(Base):

  __tablename__ = 'contact'

  """
  Standard table.

  This is an early and imperfect table. The current structure combines information 
  related to property owners and the companies, contractors, and design professionals 
  doing the work.

  SOURCES:
  --------------------------------------------------------------------------------------
  When this data comes from the 'permit' tab: there will be only up to two records per 
  permit, one for the property owner ('owner_'), which we have 98% of the time, and one 
  for the licensed contractor ('license_pro_'), which we have 88% of the time.

  We will also look for 'related_contacts'. These are rarer (~10% of permits have 1+).
  Here we see other parties: 'business_owner_', 'local_manager_', 'developer_', 
  'developers_representative_', 'engineer_', 'individual_', 'competent_person_', 
  'resident_', and '_' (we assume this to be non-categorized).

  We create one row in this table for each contact we find that is associated with each
  permit. As such, an individual permit can generate up to 11 rows in this table,
  assuming that we see one of each type of contact. The source is stored in the 
  "which_source" field.
  """

  contact_pk = Column(BigInteger, primary_key=True, unique=True, index=True)
  permit_pk = Column(BigInteger, ForeignKey('permit.permit_pk'), nullable=False)

  """ Fields related to users. """
  user_id = Column(BigInteger, nullable=True, default=None)
  user_type_id = Column(BigInteger, nullable=True, default=None)
  user_type_description = Column(String(50), nullable=True, default=None)

  """ Fields related to businesses. """
  display_name = Column(String(255), nullable=True)  # From 'permit.owner_mail_to' and 'permit.license_pro_mail_to'. 
  business_name = Column(String(255), nullable=True)  # From 'permit.owner_business' and 'permit.license_pro_business_name'. From the 'related_contacts' tab: anything in '{which_source}_business_name'.
  business_license_number = Column(String(255), nullable=True)  # From 'permit.license_pro_business_license'.
  government_agency_name = Column(String(255), nullable=True, default=None)

  """ Fields related to individuals. """
  first_name = Column(String(255), nullable=True)  #  From the 'related_contacts' tab: anything in '{which_source}_first_name'.
  last_name = Column(String(255), nullable=True)  #  From the 'related_contacts' tab: anything in '{which_source}_last_name'.
  phone_number_1 = Column(String(255), nullable=True)  # From 'permit.license_pro_phone_num_1' and 'permit.owner_phone_num_1'. From the 'related_contacts' tab: anything in '{which_source}_phone1'.
  phone_number_2 = Column(String(255), nullable=True)  # From 'permit.license_pro_phone_num_2' and 'permit.owner_phone_num_2'. From the 'related_contacts' tab: anything in '{which_source}_phone2'.
  phone_number_3 = Column(String(255), nullable=True)  # From 'permit.license_pro_phone_num_3' and 'permit.owner_phone_num_3'. From the 'related_contacts' tab: anything in '{which_source}_phone3'.
  email_address = Column(String(255), nullable=True)  # From ''permit.license_pro_email'' and 'permit.owner_email'.From the 'related_contacts' tab: anything in '{which_source}_email'.
  address = Column(Text, nullable=True, default=list)  # When this data comes from the 'related_contacts' area: append '{which_source}_address' + ', ' + '{which_source}_region'. When this comes from 'permit', join these strings in this order: (('{which_source}_address_line' (+ ' Unit ' + '{which_source}_unit' IF '{which_source}_unit' <> "NULL")) OR ('{which_source}_po_box' IF '{which_source}_address_line' == "NULL" + ', ')) + '{which_source}_city' + ', ' + '{which_source}_state' + ', ' + '{which_source}_zip'
  
  """ Storing detailed JSONB information for later. """
  property_ownership =  Column(JSONB, nullable=True, default=dict)  # We may use this field later.
  qa_license = Column(JSONB, nullable=True, default=dict)
  workers_comp = Column(JSONB, nullable=True, default=dict)

  """ Booleans that relate to contractors. """
  is_active = Column(Boolean, nullable=True, default=None)
  is_suspended = Column(Boolean, nullable=True, default=None)
  is_verified = Column(Boolean, nullable=True, default=None)
  is_deleted = Column(Boolean, nullable=True, default=None)
  is_contractor = Column(Boolean, nullable=True)  # WHEN 'which_source' == "Licensed Professional" THEN "True" ELSE "False".
  is_design_professional = Column(Boolean, nullable=True)  # WHEN 'which_source' == "Engineer" THEN "True" ELSE "False".
  is_utility_company = Column(Boolean, nullable=True, default=None)
  which_source = Column(String(255), nullable=True)  # From the 'permit' tab: WHEN "license_pro_" THEN "Licensed Professional", WHEN "owner_" THEN "Owner". From the 'related_contacts' tab: WHEN "_" THEN "Uncategorized", WHEN "business_owner_" THEN "Business Owner", WHEN "competent_person_" THEN "Competent Person", WHEN "developer_" THEN "Developer", WHEN "developers_representative_" THEN "Developer Representative", WHEN "engineer_" THEN "Engineer", WHEN "individual_" THEN "Individual", WHEN "local_manager_" THEN "Local Manager", WHEN "resident_" THEN "Resident".

  """ Dates related to the contact. """
  date_entered = Column(DateTime, nullable=True)  # From ''.
  date_updated = Column(DateTime, nullable=True)  # From ''.
  created_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)