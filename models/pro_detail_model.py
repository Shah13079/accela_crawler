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

class PropertyDetail(Base):
  __tablename__ = 'property_detail'

  """
  Standard table with custom fields linked to the permit-level.

  This is detailed information about a given address at the time of the permit 
  that may or may not change over time (we have not studied to confirm this yet). 
  This information is linked to the 'permit_pk' and 'property_address_pk' so we 
  do not throw away information as it changes over time (i.e. as new permits log
  updated information, we also keep the past state as of the previous permit(s)).
  """
  id = Column(BigInteger, primary_key=True, autoincrement=True)
  property_address_pk = Column(BigInteger, ForeignKey('property_address.property_address_pk'), nullable=False)
  property_owner_pk = Column(BigInteger, ForeignKey('contact.contact_pk'), nullable=True)
  permit_pk = Column(BigInteger, ForeignKey('permit.permit_pk'), nullable=False)

  """ Address information. """
  total_cost_job_valuation = Column(Numeric(1000, 2), nullable=True)  # From 'application_info.job_cost_valuation'. ASSUMED TO BE: The impact of the job on property value, as estimated.
  total_site_improvement_cost_raw = Column(Numeric(1000, 2), nullable=True)  # From 'application_info.cost'. ASSUMED TO BE: The cost to the contractor for materials.
  total_site_improvement_cost_clean = Column(Numeric(1000, 2), nullable=True, default=None)
  address_previous_use_description = Column(String(255), nullable=True)  # From 'application_info.previous_use'.
  address_proposed_use_description = Column(String(255), nullable=True)  # From 'application_info.proposed_use'.

  """ Over-arching parcel information. """
  parcel_zoning = Column(String(255), nullable=True)  # From 'application_info.zoning_designation'.
  parcel_zoning_subtype = Column(String(255), nullable=True)  # From 'application_info.zoning_sub_type'. 
  parcel_zoning_description = Column(String(255), nullable=True)  # From 'application_info.sub_type_other_description'.
  parcel_id = Column(String(255), nullable=True)  # From 'application_info.parcel_number'.
  parcel_block = Column(String(255), nullable=True)  # From 'application_info.parcel_block'.
  parcel_lot = Column(String(255), nullable=True)  # From 'application_info.parcel_lot'.
  parcel_subdivision = Column(String(255), nullable=True)  # From 'application_info.parcel_subdivision'.
  parcel_flood_zone = Column(String(255), nullable=True)  # From 'application_info.floodplain_designation'.

  """ Structure characteristics. """
  occupancy_load = Column(Integer, nullable=True)  # From 'application_info.max_occupancy_load'. The maximum number of people permitted in a space to ensure safe evacuation in an emergency
  count_bedrooms = Column(Integer, nullable=True, default=None)
  count_full_baths = Column(Integer, nullable=True, default=None)
  count_half_baths = Column(Integer, nullable=True, default=None)
  count_stories = Column(Integer, nullable=True)  # From 'application_info.number_of_stories' and 'application_info.stories'.
  setback_ft = Column(Numeric(12, 2), nullable=True)  # From 'application_info.setback_distance'. The distance from the property line to the building structure.
  height_ft = Column(Numeric(12, 2), nullable=True)  # From 'application_info.height'. The height of the building in feet.
  length_ft = Column(Numeric(12, 2), nullable=True)  # From 'application_info.length'. The length of the building in feet.
  width_ft = Column(Numeric(12, 2), nullable=True)  # From 'application_info.width'. The width of the building in feet.
  weight_lb = Column(Numeric(12, 2), nullable=True)  # From 'application_info.weight'. The weight of the building in pounds.
  area_property_sq_ft = Column(Integer, nullable=True)  # From 'application_info.total_area_square_footage_of_property' and 'application_info.property_square_feet'.
  area_disturbed_sq_ft = Column(Integer, nullable=True)  # From 'application_info.disturbed_area'.
  area_enclosed_sq_ft = Column(Integer, nullable=True)  # From 'application_info.square_footage' and 'application_info.total_sf_after_addition' and 'application_info.sq_ft_of_building_being_demolished'.
  area_enclosed_existing_sq_ft = Column(Integer, nullable=True)  # From 'application_info.existing_primary_structure'. The square footage of the existing structure before any additions or modifications.
  area_enclosed_proposed_sq_ft = Column(Integer, nullable=True)  # From 'application_info.proposed_structure'. This appears additive to existing area, not net of anything previously built, in most cases.

  """ Multi-family/commercial development characteristics. """
  count_buildings = Column(Integer, nullable=True)  # From 'application_info.number_of_buildings'.
  count_multifam_units = Column(Integer, nullable=True)  # From MAX of 'application_info.number_of_dwelling_units' and 'application_info.number_of_proposed_dwelling_units' and 'application_info.number_of_living_units' and 'application_info.multi_family_units' and 'application_info.#_of_multi_family_units' and 'application_info.additional_units'.

  """ Mobile home characteristics. """
  pass

  # Permit-level items:

  """ Specific industries: framing, pools, and roofing. """
  roof_slope_degrees = Column(Integer, nullable=True)  # From 'application_info.roof_pitch'.
  construction_type = Column(String(255), nullable=True)  # 'application_info.residential_construction_type_code_1' and 'application_info.construction_type_code_1' and 'application_info.construction_type_code_2'. Proceed in that order: use the next if the first is NULL, the leave NULL if none are present.
  yard_location = Column(String(255), nullable=True)  # From 'application_info.yard'. 

  """ Fire systems. """
  is_smoke_detector_required = Column(Boolean, nullable=True)  # From 'application_info.smoke_detector_required'. Map "0" to "NULL", "Yes" to "True", and "No" to "False". Indicates if a smoke detector is required for the building.
  is_sprinkler_required = Column(Boolean, nullable=True)  # From 'application_info.sprinkler_required'. Map "0" to "NULL", "Yes" to "True", and "No" to "False". Indicates if a sprinkler system is required for the building.
  
  """ HVAC systems. """
  count_heaters = Column(Integer, nullable=True)  # From 'application_info.heater'. The number of heaters in the building.
  count_boilers_under_100000_btu = Column(Integer, nullable=True)  # From 'application_info.boiler_compressor_0_to_100000_btu_or_up_to_3_horsepower'.
  count_boilers_over_100001_btu = Column(Integer, nullable=True)  # From 'application_info.boiler_compressor_100001_and_500000_btu_or_4_15_horsepower' + 'application_info.boiler_compressor_100001_and_500000_btu_or_4_15_horsepower' + 'application_info.boiler_compressor_500001_to_1000000_btu_or_16_30_horsepower' + 'application_info.boiler_compressor_1000001_to_1750000_btu_or_31_50_horsepower' + 'application_info.boiler_compressor_1750000plus_btu_or_51_horsepower'.
  count_furnaces_under_100000_btu_hr = Column(Integer, nullable=True)  # From 'application_info.furnace_0_to_10000_btu_hr'.
  count_furnaces_over_100001_btu_hr = Column(Integer, nullable=True)  # From 'application_info.furnace_100001plus_btu_hr'.
  count_air_units_under_10000_cfm = Column(Integer, nullable=True)  # From 'application_info.air_handling_units_up_to_including_10000_cfm_including_any_attached_ducts'.
  count_air_units_over_10001_cfm = Column(Integer, nullable=True)  # From 'application_info.air_handling_units_10001plus_cfm_including_any_attached_ducts'.

  """ Other commercial systems. """
  heating_source = Column(String(255), nullable=True)  # From 'application_info.heating_source'. The type of heating system used in the building: electric, LNG, etc.
  water_supply = Column(String(255), nullable=True)  # From 'application_info.water_supply'. The source of water for the building, such as municipal supply or well.

  """ Un-parsed lists of dictionaries. To be structured or deleted later. """
  unstructured_additional_details = Column(JSONB, nullable=True, default=dict)  # Everything in 'application_info' that starts with "#0.". Examples: "1._bathtub_or_tub/shower_combination" and "37._gray_water_system". Add here as K-V pairs. The keys/titles do not need to be parsed/cleaned.
  unstructured_description = Column(Text, nullable=True)  # From 'application_info.other_title'.

  """ Misc. categorigal string fields. """
  demolition_detail = Column(String(255), nullable=True)  # From 'application_info.demolition_type'. How much is getting demolished.
  demolition_structure_type = Column(String(255), nullable=True)  # From 'application_info.occupancy'. Details the type of structure getting demolished.
  structure_category = Column(String(255), nullable=True)  # From 'application_info.category'.
  structure_category_size = Column(String(255), nullable=True)  # From 'application_info.category_size'.
  commercial_structure_type = Column(String(255), nullable=True)  # From 'application_info.if_this_permit_is_for_a_residential_dwelling_select_the_correct_occupancy_type' and 'application_info.if_permit_is_for_a_single_family_home_storage_building_detached_garage_duplex_or_triplex_select_the_occupancy_type' and 'application_info.if_permit_is_for_a_single_family_dwelling_duplex_or_triplex_select_the_occupancy_type'. Fill them in that order, if none are present, leave NULL.
  commercial_structure_subtype = Column(String(255), nullable=True)  # From 'application_info.commercial_subtype'.
  residential_structure_type = Column(String(255), nullable=True)  # From 'application_info.if_this_permit_is_for_a_commercial_building_select_the_occupancy_type' and 'application_info.if_permit_is_for_a_commercial_building_select_the_occupancy_type' and 'application_info.if_this_permit_is_for_a_commercial_building_select_the_correct_occupancy_type'. Fill them in that order, if none are present, leave NULL.
  residential_structure_subtype = Column(String(255), nullable=True)  # From 'application_info.residential_subtype'.

  """ Boolean fields. """
  is_commercial = Column(Boolean, nullable=True)  # From 'application_info.commercial'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_mechanical = Column(Boolean, nullable=True)  # From 'application_info.mechanical'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_electrical = Column(Boolean, nullable=True)  # From 'application_info.electrical' or 'application_info.is_your_permit_for_low_voltage_work'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_plumbing = Column(Boolean, nullable=True)  # From 'application_info.plumbing'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_gas = Column(Boolean, nullable=True)  # From 'application_info.installation_of_gas_outlets'. WHEN > 0 THEN "True", WHEN 0 THEN "False". Otherwise "NULL".
  is_drywell_or_sump = Column(Boolean, nullable=True)  # From 'application_info.drywell_sump'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_new_construction = Column(Boolean, nullable=True)  # From 'application_info.new_construction'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_residential = Column(Boolean, nullable=True)  # From 'application_info.is_this_permit_for_a_residential_building'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_demolition = Column(Boolean, nullable=True)  # From 'application_info.structure_demolition'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_addition = Column(Boolean, nullable=True)  # From 'application_info.addition'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_remodel_or_addition = Column(Boolean, nullable=True)  # From 'application_info.addition'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_reroof = Column(Boolean, nullable=True)  # From 'application_info.reroof'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_reside = Column(Boolean, nullable=True)  # From 'application_info.reside'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_repair = Column(Boolean, nullable=True)  # From 'application_info.repair'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_remodel = Column(Boolean, nullable=True)  # From 'application_info.remodel'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_slab = Column(Boolean, nullable=True)  # From 'application_info.slab'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_basement = Column(Boolean, nullable=True)  # From 'application_info.basement'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_crawl_space = Column(Boolean, nullable=True)  # From 'application_info.crawl_space'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_shell_only = Column(Boolean, nullable=True)  # From 'application_info.shell_only'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_tenant_improvement = Column(Boolean, nullable=True)  # From 'application_info.tenant_improvement'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_landscaping = Column(Boolean, nullable=True)  # From 'application_info.landscaping'. Map "0" to "NULL", "Yes" to "True", and "No" to "False". We may remove this field later due to low occurrence.
  is_change_of_use = Column(Boolean, nullable=True)  # From 'application_info.change_of_use'. Map "0" to "NULL", "Yes" to "True", and "No" to "False".
  is_zcp_required = Column(Boolean, nullable=True)  # From 'application_info.zcp_required'. Map "0" to "NULL", "Yes" to "True", and "No" to "False". A Zoning Compliance Permit ("ZCP") is an administrative permit issued by a local authority (like a town or city) to ensure that a proposed project or activity aligns with the town's zoning regulations, often found in a Unified Development Ordinance ("UDO"). These regulations dictate how land can be used in different areas, covering aspects like building heights, lot coverage, and allowed activities.
  is_within_city_limits = Column(Boolean, nullable=True)  # From 'application_info.within_city_limits'. Map "0" to "NULL", "Yes" to "True", and "No" to "False". We may remove this field later due to low occurrence.
  created_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)