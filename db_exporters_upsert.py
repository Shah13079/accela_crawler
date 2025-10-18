import os
import logging
import math, re, json
from decimal import Decimal
from sqlalchemy.orm import Session
from models.models_base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dateutil.parser import ParserError
from sqlalchemy.orm import sessionmaker
from dateutil.parser import ParserError
from sqlalchemy.exc import SQLAlchemyError, MultipleResultsFound
from dateutil.parser import parse as parse_datetime, ParserError

from models.permit_model import Permit
from models.contact_model import Contact
from models.pro_detail_model import PropertyDetail
from models.process_model import PermitProcess  
from models.related_model import PermitRelated
from models.pro_detail_model import PropertyDetail
from models.inspection_model import PermitInspection
from models.valuation_model import PermitValuation
from models.condition_model import PermitCondition
from models.property_address_model import PropertyAddress

from utilities import (
    parse_formate_address,
    format_address_for_client,
    extract_permit_primary_number,
    parse_mmddyyyy,
    
)

logger = logging.getLogger(__name__)

def _blank_to_none(raw):
    if raw is None:
        return None
    s = str(raw).strip()
    return None if (s == "" or s.upper() == "NULL" or s == "--") else raw

def _clean_dict(d: dict) -> dict:
        cleaned = {}
        for k, v in d.items():
            # if it’s a float NaN, turn into None
            if isinstance(v, float) and math.isnan(v):
                cleaned[k] = None
            else:
                cleaned[k] = v
        return cleaned


class DatabaseConnection:
    #db coneection initilization
    def __init__(self, db_url=None):
        if db_url is None:
          
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, 'config.json')
            
          
            try:
                with open(config_path, 'r') as config_file:
                    config = json.load(config_file)
                    db_url = config.get('database', {}).get('url')
                    
                    if not db_url:
                        db_url = config.get('db_url')
                        
                    if not db_url:
                        raise ValueError("Database URL not found in config.json. "
                                       "Please add it under 'db_url'")
                        
            except FileNotFoundError:
                raise FileNotFoundError(f"config.json not found at {config_path}. "
                                      "Please create it in the same directory as this Python file.")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in config.json: {e}")
        
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
            
    def create_tables(self):
        """Create all tables in the database"""
        try:
          
            Base.metadata.create_all(self.engine)
          
            logger.info("Database tables created successfully")
        except SQLAlchemyError as e:
            logger.error(f"Error creating database tables: {str(e)}")
            raise
        
    def get_session(self):
        """Return a new session"""
        return self.Session()
    

class PermitExporter:
    def __init__(self, db_connection):
        # db_connection is your DatabaseConnection instance
        self.session: Session = db_connection.get_session()

    def upsert(self,
               permit_basic_data: dict,
               app_parcel_info_row: dict,
               processing_info: list,
               property_address_pk: int,
               property_owner_pk: int = None,
               contractor_company_pk: int = None,
            #    contractor_primary_pk: int = None,
            #    contractor_designer_pk: int = None
    ) -> Permit:
        """
        Inserts a new Permit or updates an existing one (where is_completed=False)
        based on full_permit_number.
        """
        # 1) Clean inputs
        basic = _clean_dict(permit_basic_data)
        app   = _clean_dict(app_parcel_info_row)

        # 2) Derive all the column values exactly as before
        full_num = basic.get("permit_number")
        raw_cat  = (basic.get("category") or "").lower()
        primary  = extract_permit_primary_number(full_num)
        category = "Residential" if "residential" in raw_cat else "Non-Residential"

        # parse completedate
        raw_done = app.get("completedate")
        if not (isinstance(raw_done, str)
                and raw_done.strip()
                and raw_done.strip().lower() != "null"):
            date_work_completed = None
        else:
            date_work_completed = parse_mmddyyyy(raw_done)

        date_req = date_iss = None
        is_completed = False
        for step in processing_info:
            ps, st, sub, ms = (
                step.get("process_step"),
                step.get("status"),
                step.get("sub_step_type"),
                step.get("marked_status"),
            )
            if ps == "Application Intake" and st == "Complete" and sub == "Bold" and ms == "Complete":
                date_req = step.get("activated_date")
            if ps == "Issue Permit" and st == "Complete" and sub == "Bold" and ms == "Complete":
                date_iss = step.get("marked_date")
            if (
                ps == "Complete" and st == "Complete" and sub == "Bold"
                and isinstance(ms, str)
                and ms.strip().lower() in {
                    "c of o issued","complete","final","refunded","void","withdrawn"
                }
            ):
                is_completed = True

        # cost fallback
        fallback = app.get("project_cost_includes_all_labor_materials")
        raw_cost = app.get("project_cost") or fallback
        total_cost_raw = (
            Decimal(raw_cost)
            if raw_cost not in (None, "", "NULL")
            else None
        )

        # aggregate all values into one dict
        vals = {
            "total_cost_raw":          total_cost_raw,
            "full_permit_number":      full_num,
            "permit_primary_number":   primary,
            "permit_category":         category,
            "permit_type_description": basic.get("permit_type"),
            "status_description":      basic.get("status"),
            "proposed_use_description": app.get("proposed_use"),
            "work_type_description":   None,
            "work_description":        basic.get("description"),

            "date_permit_requested":   date_req,
            "date_permit_issued":      date_iss,
            "date_permit_final":       _blank_to_none(app.get("end_date")),
            "date_permit_expired":     _blank_to_none(app.get("permit_expiration_date")),
            "date_work_started":       _blank_to_none(app.get("startdate")),
            "date_work_expected":      _blank_to_none(app.get("targetdate")),
            "date_work_completed":     date_work_completed,
            "is_completed":            is_completed,

            "permit_url":              basic.get("permit_url"),

            "property_address_pk":     property_address_pk,
            "property_owner_pk":       property_owner_pk,
            "contractor_company_pk":   contractor_company_pk,
            #"contractor_primary_pk":   contractor_primary_pk,
            #"contractor_designer_pk":  contractor_designer_pk,
            "permit_company_id":       None,
        }

        try:
            # 3) Attempt to find an existing, incomplete permit
            existing = (
                self.session
                    .query(Permit)
                    .filter_by(full_permit_number=full_num)
                    .one_or_none()
            )

            if existing:
                # 4a) UPDATE in place
                for col, val in vals.items():
                    setattr(existing, col, val)
                self.session.commit()
                # ensure any defaults or triggers are loaded
                self.session.refresh(existing)
                return existing

            # 4b) INSERT brand-new
            new = Permit(**vals)
            self.session.add(new)
            self.session.commit()
            self.session.refresh(new)
            return new

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"[PermitExporter.upsert] {e}")
            raise

    def close(self):
        self.session.close()

class PropertyAddressExporter:
    def __init__(self, db_connection):
        self.session: Session = db_connection.get_session()

    def upsert(self, permit_data: dict, app_parcel_info: dict) -> PropertyAddress:
        """
        Always ensure one PropertyAddress per permit:
        1) If the Permit record already points at an address, update that row.
        2) Otherwise insert a fresh PropertyAddress.
        No longer deduplicating by parcel_id or address_full.
        """
        # Normalize the raw listing‐page address
        raw_address = permit_data.get("address")
        if not (isinstance(raw_address, str) and raw_address.strip() and raw_address.strip().upper() != "NULL"):
            formatted_address = None
            components = {k: None for k in (
                "street_number","street_name","street_type","street_unit",
                "city","state","postal_code"
            )}
        else:
            components = parse_formate_address(raw_address)
            formatted_address = format_address_for_client(components)

        # Build our column/value dict
        vals = {
            "parcel_id":    _blank_to_none(app_parcel_info.get("parcel_number")),
            "address_base": _blank_to_none(permit_data.get("work_location")),
            "address_full": formatted_address,
            "street_number": components["street_number"],
            "street_name":   components["street_name"],
            "street_type":   components["street_type"],
            "street_unit":   components["street_unit"],
            "city":          components["city"],
            "state":         components["state"],
            "postal_code":   components["postal_code"],
        }

        existing = None

        # 1) Look up the permit's current FK
        permit_number = permit_data.get("permit_number")
        if permit_number:
            try:
                perm = (
                    self.session
                        .query(Permit)
                        .filter_by(full_permit_number=permit_number)
                        .one_or_none()
                )
                if perm and perm.property_address_pk:
                    existing = self.session.get(PropertyAddress, perm.property_address_pk)
            except SQLAlchemyError as e:
                logger.warning(f"[PropertyAddressExporter] failed to fetch permit {permit_number}: {e}")

        try:
            if existing:
                # 2a) update in place
                for col, val in vals.items():
                    setattr(existing, col, val)
                self.session.commit()
                self.session.refresh(existing)
                return existing

            # 2b) insert brand-new row
            new = PropertyAddress(**vals)
            self.session.add(new)
            self.session.commit()
            self.session.refresh(new)
            return new

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"[PropertyAddressExporter.upsert] {e}")
            raise

    def close(self):
        self.session.close()



class ContactExporter:
    def __init__(self, db_connection):
        self.session: Session = db_connection.get_session()

        # Map your short prefixes to the human-readable "which_source" string
        self.source_map = {
            'owner': 'Owner',
            'license_pro': 'Licensed Professional',
            'business_owner': 'Business Owner',
            'competent_person': 'Competent Person',
            'developer': 'Developer',
            'developers_representative': 'Developer Representative',
            'engineer': 'Engineer',
            'individual': 'Individual',
            'local_manager': 'Local Manager',
            'resident': 'Resident',
            '_': 'Uncategorized'
        }
        
    def _construct_address(self, data: dict, prefix: str) -> str:
        # ... your existing address logic ...
        base = data.get(f"{prefix}_address")
        region = data.get(f"{prefix}_region")
        if base and isinstance(base, str) and base.strip():
            if region and isinstance(region, str) and region.strip():
                return f"{base.strip()}, {region.strip()}"
            return base.strip()

        parts = []
        # [rest of your address formatting code]

        return ", ".join(parts) if parts else None

    def upsert(self, contact_data: dict, permit_pk: int, prefix: str) -> Contact:
        """
        Inserts or updates a Contact for this (permit_pk, which_source).
        If multiple already exist, updates the first and leaves the extras alone.
        """
        mapped_source = self.source_map.get(prefix, prefix)
        address = self._construct_address(contact_data, prefix)

        vals = {
            # user fields
            "user_id":               contact_data.get(f"{prefix}_user_id"),
            "user_type_id":          contact_data.get(f"{prefix}_user_type_id"),
            "user_type_description": contact_data.get(f"{prefix}_user_type_description"),
            # business fields
            "display_name":            contact_data.get(f"{prefix}_mail_to"),
            "business_name":           (contact_data.get(f"{prefix}_business")
                                        or contact_data.get(f"{prefix}_business_name")),
            "business_license_number": contact_data.get(f"{prefix}_business_license"),
            "government_agency_name":  contact_data.get(f"{prefix}_government_agency_name"),
            # individual fields
            "first_name":    contact_data.get(f"{prefix}_first_name"),
            "last_name":     contact_data.get(f"{prefix}_last_name"),
            "phone_number_1":(contact_data.get(f"{prefix}_phone_num_1")
                              or contact_data.get(f"{prefix}_phone1")),
            "phone_number_2":(contact_data.get(f"{prefix}_phone_num_2")
                              or contact_data.get(f"{prefix}_phone2")),
            "phone_number_3":(contact_data.get(f"{prefix}_phone_num_3")
                              or contact_data.get(f"{prefix}_phone3")),
            "email_address": contact_data.get(f"{prefix}_email"),
            "address":       address,
            # JSONB blobs
            "property_ownership": contact_data.get(f"{prefix}_property_ownership") or {},
            "qa_license":         contact_data.get(f"{prefix}_qa_license")       or {},
            "workers_comp":       contact_data.get(f"{prefix}_workers_comp")     or {},
            # boolean flags
            "is_active":             contact_data.get(f"{prefix}_is_active"),
            "is_suspended":          contact_data.get(f"{prefix}_is_suspended"),
            "is_verified":           contact_data.get(f"{prefix}_is_verified"),
            "is_deleted":            contact_data.get(f"{prefix}_is_deleted"),
            "is_contractor":         (mapped_source == "Licensed Professional"),
            "is_design_professional":(mapped_source == "Engineer"),
            "is_utility_company":    contact_data.get(f"{prefix}_is_utility_company"),
            "which_source":          mapped_source,
            "date_entered":          contact_data.get(f"{prefix}_date_entered"),
            "date_updated":          contact_data.get(f"{prefix}_date_updated"),
        }

        try:
           
            existing = (
                self.session
                    .query(Contact)
                    .filter_by(permit_pk=permit_pk, which_source=mapped_source)
                    .first()
            )

            if existing:
                # update in place
                for col, val in vals.items():
                    setattr(existing, col, val)
                self.session.commit()
                self.session.refresh(existing)
                return existing

            # otherwise insert new
            new = Contact(permit_pk=permit_pk, **vals)
            self.session.add(new)
            self.session.commit()
            self.session.refresh(new)
            return new

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"[ContactExporter.upsert] {e}")
            raise

    def close(self):
        self.session.close()



class PropertyDetailExporter:
    def __init__(self, db_connection):
        self.session = db_connection.get_session()

    def _as_decimal(self, raw):
        try:
            return Decimal(raw) if raw not in (None, "", "NULL") else None
        except:
            return None

    def _as_int(self, raw):
        try:
            return int(raw) if raw not in (None, "", "NULL") else None
        except:
            return None

    def _as_bool(self, raw):
        if raw in (None, "", "0", "NULL"):
            return None
        r = str(raw).strip().lower()
        if r in ("yes", "y", "true", "t", "1"):
            return True
        if r in ("no", "n", "false", "f", "0"):
            return False
        return None

    def _blank_to_none(self, raw):
        """All-caps “NULL”, empty, whitespace, or “--” ➔ None"""
        if raw is None:
            return None
        s = str(raw).strip()
        return None if (s == "" or s.upper() == "NULL" or s == "--") else raw

    def upsert(self,
                     permit_pk: int,
                     property_address_pk: int,
                     property_owner_pk: int,
                     app: dict
    ) -> PropertyDetail:
        """
        UPSERT PropertyDetail on (permit_pk, property_address_pk). If one exists
        already, update its fields; otherwise insert a new row.
        """
        # normalize NaN → None
        clean_app = {
            k: (None if isinstance(v, float) and math.isnan(v) else v)
            for k, v in app.items()
        }

        # ASIT‐style unstructured fields
        unstr = {}
        for raw_key, raw_val in clean_app.items():
            if re.match(r'^\d+', raw_key):
                name = re.sub(r'^\d+[\._]*', '', raw_key)
                key = re.sub(r'[^0-9A-Za-z]+', '_', name).strip('_').lower()
                if not (isinstance(raw_val, str) and raw_val.strip().lower() == "null"):
                    unstr[key] = raw_val

        # blanks → None
        parcel_id          = self._blank_to_none(clean_app.get("parcel_number"))
        parcel_block       = self._blank_to_none(clean_app.get("parcel_block"))
        parcel_lot         = self._blank_to_none(clean_app.get("parcel_lot"))
        parcel_subdivision = self._blank_to_none(clean_app.get("parcel_subdivision"))
        heating_source     = self._blank_to_none(clean_app.get("heating_source"))
        water_supply       = self._blank_to_none(clean_app.get("water_supply"))
        unstr_desc         = self._blank_to_none(clean_app.get("other_title"))

        # aggregate all values into one dict
        vals = {
            # "property_owner_pk":               property_owner_pk,
            "total_cost_job_valuation":        self._as_decimal(clean_app.get("job_cost_valuation")),
            "total_site_improvement_cost_raw": self._as_decimal(clean_app.get("cost")),
            "total_site_improvement_cost_clean": None,
            "address_previous_use_description": clean_app.get("previous_use"),
            "address_proposed_use_description": clean_app.get("proposed_use"),

            "parcel_zoning":             clean_app.get("zoning_designation"),
            "parcel_zoning_subtype":     clean_app.get("zoning_sub_type"),
            "parcel_zoning_description": clean_app.get("sub_type_other_description"),
            "parcel_id":                 parcel_id,
            "parcel_block":              parcel_block,
            "parcel_lot":                parcel_lot,
            "parcel_subdivision":        parcel_subdivision,
            "parcel_flood_zone":         clean_app.get("floodplain_designation"),

            "occupancy_load":            self._as_int(clean_app.get("max_occupancy_load")),
            "count_bedrooms":            self._as_int(clean_app.get("number_of_bedrooms")),
            "count_full_baths":          self._as_int(clean_app.get("full_baths")),
            "count_half_baths":          self._as_int(clean_app.get("half_baths")),
            "count_stories":             self._as_int(clean_app.get("number_of_stories") or clean_app.get("stories")),
            "setback_ft":                self._as_decimal(clean_app.get("setback_distance")),
            "height_ft":                 self._as_decimal(clean_app.get("height")),
            "length_ft":                 self._as_decimal(clean_app.get("length")),
            "width_ft":                  self._as_decimal(clean_app.get("width")),
            "weight_lb":                 self._as_decimal(clean_app.get("weight")),
            "area_property_sq_ft":       self._as_int(clean_app.get("total_area_square_footage_of_property")
                                                    or clean_app.get("property_square_feet")),
            "area_disturbed_sq_ft":      self._as_int(clean_app.get("disturbed_area")),
            "area_enclosed_sq_ft":       self._as_int(clean_app.get("square_footage")
                                                    or clean_app.get("total_sf_after_addition")
                                                    or clean_app.get("sq_ft_of_building_being_demolished")),
            "area_enclosed_existing_sq_ft": self._as_int(clean_app.get("existing_primary_structure")),
            "area_enclosed_proposed_sq_ft": self._as_int(clean_app.get("proposed_structure")),

            "count_buildings":       self._as_int(clean_app.get("number_of_buildings")),
            "count_multifam_units":  self._as_int(
                                           clean_app.get("number_of_dwelling_units")
                                        or clean_app.get("number_of_proposed_dwelling_units")
                                        or clean_app.get("number_of_living_units")
                                        or clean_app.get("multi_family_units")
                                        or clean_app.get("#_of_multi_family_units")
                                        or clean_app.get("additional_units")
                                      ),

            "roof_slope_degrees":     self._as_int(clean_app.get("roof_pitch")),
            "construction_type":      (
                                          clean_app.get("residential_construction_type_code_1")
                                       or clean_app.get("construction_type_code_1")
                                       or clean_app.get("construction_type_code_2")
                                      ),
            "yard_location":          clean_app.get("yard"),

            "is_smoke_detector_required": self._as_bool(clean_app.get("smoke_detector_required")),
            "is_sprinkler_required":      self._as_bool(clean_app.get("sprinkler_required")),

            "count_heaters":                   self._as_int(clean_app.get("heater")),
            "count_boilers_under_100000_btu":  self._as_int(clean_app.get(
                                                   "boiler_compressor_0_to_100000_btu_or_up_to_3_horsepower"
                                               )),
            "count_boilers_over_100001_btu":   self._as_int(
                                                   clean_app.get("boiler_compressor_100001_and_500000_btu_or_4_15_horsepower")
                                                or clean_app.get("boiler_compressor_500001_to_1000000_btu_or_16_30_horsepower")
                                                or clean_app.get("boiler_compressor_1000001_to_1750000_btu_or_31_50_horsepower")
                                                or clean_app.get("boiler_compressor_1750000plus_btu_or_51_horsepower")
                                               ),
            "count_furnaces_under_100000_btu_hr": self._as_int(clean_app.get("furnace_0_to_10000_btu_hr")),
            "count_furnaces_over_100001_btu_hr":  self._as_int(clean_app.get("furnace_100001plus_btu_hr")),
            "count_air_units_under_10000_cfm":    self._as_int(clean_app.get(
                                                   "air_handling_units_up_to_including_10000_cfm_including_any_attached_ducts"
                                               )),
            "count_air_units_over_10001_cfm":     self._as_int(clean_app.get(
                                                   "air_handling_units_10001plus_cfm_including_any_attached_ducts"
                                               )),

            "heating_source":            heating_source,
            "water_supply":              water_supply,

            "unstructured_additional_details": unstr,
            "unstructured_description":        unstr_desc,

            "demolition_detail":         clean_app.get("demolition_type"),
            "demolition_structure_type": clean_app.get("occupancy"),
            "structure_category":        clean_app.get("category"),
            "structure_category_size":   clean_app.get("category_size"),
            "commercial_structure_type": (
                                               clean_app.get(
                                                   "if_this_permit_is_for_a_residential_dwelling_select_the_correct_occupancy_type"
                                               )
                                            or clean_app.get(
                                                   "if_permit_is_for_a_single_family_home_storage_building_detached_garage_duplex_or_triplex_select_the_occupancy_type"
                                               )
                                            or clean_app.get(
                                                   "if_permit_is_for_a_single_family_dwelling_duplex_or_triplex_select_the_occupancy_type"
                                               )
                                          ),
            "commercial_structure_subtype": clean_app.get("commercial_subtype"),
            "residential_structure_type":   (
                                               clean_app.get(
                                                   "if_this_permit_is_for_a_commercial_building_select_the_occupancy_type"
                                               )
                                            or clean_app.get(
                                                   "if_permit_is_for_a_commercial_building_select_the_correct_occupancy_type"
                                               )
                                            or clean_app.get(
                                                   "if_this_permit_is_for_a_commercial_building_select_the_correct_occupancy_type"
                                               )
                                          ),
            "residential_structure_subtype": clean_app.get("residential_subtype"),

            # explicit boolean flags
            "is_commercial":            self._as_bool(clean_app.get("commercial")),
            "is_mechanical":            self._as_bool(clean_app.get("mechanical")),
            "is_electrical":            self._as_bool(
                                            clean_app.get("electrical")
                                         or clean_app.get("is_your_permit_for_low_voltage_work")
                                         ),
            "is_plumbing":              self._as_bool(clean_app.get("plumbing")),
            "is_gas":                   self._as_bool(clean_app.get("installation_of_gas_outlets")),
            "is_drywell_or_sump":       self._as_bool(clean_app.get("drywell_sump")),
            "is_new_construction":      self._as_bool(clean_app.get("new_construction")),
            "is_residential":           self._as_bool(clean_app.get("is_this_permit_for_a_residential_building")),
            "is_demolition":            self._as_bool(clean_app.get("structure_demolition")),
            "is_addition":              self._as_bool(clean_app.get("addition")),
            "is_remodel_or_addition":   self._as_bool(clean_app.get("addition")),
            "is_reroof":                self._as_bool(clean_app.get("reroof")),
            "is_reside":                self._as_bool(clean_app.get("reside")),
            "is_repair":                self._as_bool(clean_app.get("repair")),
            "is_remodel":               self._as_bool(clean_app.get("remodel")),
            "is_slab":                  self._as_bool(clean_app.get("slab")),
            "is_basement":              self._as_bool(clean_app.get("basement")),
            "is_crawl_space":           self._as_bool(clean_app.get("crawl_space")),
            "is_shell_only":            self._as_bool(clean_app.get("shell_only")),
            "is_tenant_improvement":    self._as_bool(clean_app.get("tenant_improvement")),
            "is_landscaping":           self._as_bool(clean_app.get("landscaping")),
            "is_change_of_use":         self._as_bool(clean_app.get("change_of_use")),
            "is_zcp_required":          self._as_bool(clean_app.get("zcp_required")),
            "is_within_city_limits":    self._as_bool(clean_app.get("within_city_limits")),
        }

        try:
            existing = (
                self.session
                    .query(PropertyDetail)
                    .filter_by(permit_pk=permit_pk)
                    .one_or_none()
            )

            if existing:
                # Update the existing row—this will overwrite the old address PK
                existing.property_address_pk              = property_address_pk
                existing.property_owner_pk                = property_owner_pk
                for col, val in vals.items():
                    setattr(existing, col, val)
                self.session.commit()
                self.session.refresh(existing)
                return existing
            else:
                # Insert new
                new = PropertyDetail(
                    permit_pk             = permit_pk,
                    property_address_pk   = property_address_pk,
                    property_owner_pk     = property_owner_pk,
                    **vals
                )
                self.session.add(new)
                self.session.commit()
                self.session.refresh(new)
                return new
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"[PropertyDetailExporter.process_item] {e}")
            raise

    def close(self):
        self.session.close()







logger = logging.getLogger(__name__)

class PermitInspectionExporter:
    def __init__(self, db_connection):
        self.session = db_connection.get_session()

    def upsert(self, inspections: list[dict], permit_pk: int) -> list[PermitInspection]:
        """
        Insert only new inspections that don't already exist.
        Matches entire row to determine if inspection already exists.
        """
        try:
            new_inspections = []
            processed_inspections = []
            # Get permit number for better logging
            full_num = (
                self.session
                    .query(Permit.full_permit_number)
                    .filter_by(permit_pk=permit_pk)
                    .scalar()
            ) or f"(pk={permit_pk})"
            
            # logger.info(f"Permit {full_num}: Processing {len(inspections)} inspections")

            # Get all existing inspections for this permit
            existing_inspections = (
                self.session.query(PermitInspection)
                .filter(PermitInspection.permit_pk == permit_pk)
                .all()
            )
            
            # logger.info(f"Permit {full_num}: Found {len(existing_inspections)} existing inspections")

            
            
            for i, insp in enumerate(inspections):
                # logger.debug(f"Permit {full_num}: Processing inspection {i+1}/{len(inspections)}: {insp.get('title', 'Unknown')} - {insp.get('status', 'Unknown')}")
                
                # Parse combined date+time safely
                raw_date = insp.get("date", "").strip()
                raw_time = insp.get("time", "").strip()
                dt = None
                if raw_date:
                    combo = f"{raw_date} {raw_time}" if raw_time else raw_date
                    try:
                        dt = parse_datetime(combo)
                    except (ParserError, ValueError):
                        logger.warning(f"Permit {full_num}: Could not parse datetime '{combo}'")
                        dt = None

                # Get status and normalize it
                status = (insp.get("status") or "").strip()
                status_lower = status.lower()

                # === BOOLEAN FIELDS (Fixed based on model comments) ===
                # is_required: "False" WHEN source == "Optional", "True" otherwise
                is_required = insp.get("is_required", True)
                
                # is_scheduled: True if status is "Scheduled", otherwise check if it's scheduled
                is_scheduled = status_lower == "scheduled" if status_lower else True
                
                # is_failed: "True" WHEN status == "Fail", "False" otherwise
                is_failed = status_lower == "fail"
                
                # is_passed: "True" WHEN status == "Pass", "False" otherwise
                is_passed = status_lower == "pass"
                
                # is_completed: "True" WHEN status IN ("Pass","Fail","Cancelled"), "False" otherwise
                is_completed = status_lower in ["pass", "fail", "cancelled"]

                # === DATE FIELDS (Fixed based on model comments) ===
                # date_completed: Set ONLY when status is "Pass"
                date_completed = dt if status_lower == "pass" else None
                
                # date_canceled: Set ONLY when status is "Cancelled"
                date_canceled = dt if status_lower == "cancelled" else None
                
                # date_updated: Always set to the inspection date/time
                date_updated = dt

                # === CREATE INSPECTION DATA ===
                inspector_name = insp.get("result_by") if insp.get("result_by") and insp.get("result_by") != "unassigned" else None
                comments = insp.get("comments")
                if comments is None:
                    comments = {}

                inspection_data = {
                    "permit_pk": permit_pk,
                    "actual_inspector_name": inspector_name,
                    "default_inspector_username": insp.get("default_inspector_username"),
                    "actual_performed_by_name": insp.get("actual_performed_by_name"),
                    "inspection_type_description": insp.get("title"),
                    "discipline_type_description": insp.get("discipline_type_description"),
                    "comments": comments,
                    "is_required": is_required,
                    "is_scheduled": is_scheduled,
                    "is_failed": is_failed,
                    "is_passed": is_passed,
                    "is_completed": is_completed,
                    "which_source": "inspection",
                    "date_requested": insp.get("date_requested"),
                    "date_started": insp.get("date_started"),
                    "date_completed": date_completed,
                    "date_canceled": date_canceled,
                    "date_entered": insp.get("date_entered"),
                    "date_updated": date_updated,
                }

                # Check if this exact inspection already exists in DB OR in current batch
                if not self._inspection_exists(existing_inspections, inspection_data) and \
                not self._inspection_exists(processed_inspections, inspection_data):
                    # Create new inspection only if it doesn't exist
                    new_inspection = PermitInspection(**inspection_data)
                    self.session.add(new_inspection)
                    new_inspections.append(new_inspection)
                    processed_inspections.append(new_inspection)  
                else:
                    logger.debug(f"Skipping duplicate inspection: {inspection_data.get('inspection_type_description')}")
                   
            # Commit only new inspections
            if new_inspections:
                self.session.commit()
                
                # Refresh all new records to get their IDs
                for inspection in new_inspections:
                    self.session.refresh(inspection)
              
            return new_inspections
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"[PermitInspectionExporter.upsert] Error for permit {permit_pk}: {e}")
            raise

    def _inspection_exists(self, existing_inspections: list[PermitInspection], new_data: dict) -> bool:
        """
        Check if an inspection with matching data already exists.
        Compares all relevant fields to determine uniqueness.
        """
        for existing in existing_inspections:
            # Compare all relevant fields (excluding auto-generated IDs)
            if (
                existing.actual_inspector_name == new_data.get("actual_inspector_name") and
                existing.default_inspector_username == new_data.get("default_inspector_username") and
                existing.actual_performed_by_name == new_data.get("actual_performed_by_name") and
                existing.inspection_type_description == new_data.get("inspection_type_description") and
                existing.discipline_type_description == new_data.get("discipline_type_description") and
                existing.is_required == new_data.get("is_required") and
                existing.is_scheduled == new_data.get("is_scheduled") and
                existing.is_failed == new_data.get("is_failed") and
                existing.is_passed == new_data.get("is_passed") and
                existing.is_completed == new_data.get("is_completed") and
                existing.which_source == new_data.get("which_source") and
                self._dates_match(existing.date_requested, new_data.get("date_requested")) and
                self._dates_match(existing.date_started, new_data.get("date_started")) and
                self._dates_match(existing.date_completed, new_data.get("date_completed")) and
                self._dates_match(existing.date_canceled, new_data.get("date_canceled")) and
                self._dates_match(existing.date_entered, new_data.get("date_entered")) and
                self._dates_match(existing.date_updated, new_data.get("date_updated")) and
                self._comments_match(existing.comments, new_data.get("comments"))
            ):
                return True
        return False

    def _dates_match(self, date1, date2) -> bool:
        """Compare two dates, handling None values and timezone differences."""
        if date1 is None and date2 is None:
            return True
        if date1 is None or date2 is None:
            return False
        # Compare dates without microseconds for practical matching
        return date1.replace(microsecond=0) == date2.replace(microsecond=0) if hasattr(date1, 'replace') and hasattr(date2, 'replace') else date1 == date2

    def _comments_match(self, comments1, comments2) -> bool:
        """Compare comments fields (JSONB), handling None values."""
        if comments1 is None and comments2 is None:
            return True
        if comments1 is None or comments2 is None:
            return False
        return comments1 == comments2

    def close(self):
        self.session.close()

class PermitValuationExporter:
    def __init__(self, db_connection):
        self.session = db_connection.get_session()

    def _parse_money(self, s):
        if not s or not isinstance(s, str):
            return None
        cleaned = s.replace('$', '').replace(',', '').strip()
        try:
            return Decimal(cleaned)
        except:
            return None

    def upsert(self, permit_pk: int, valuation_list: list):
        """
        Upsert each row in valuation_list by matching on
        (permit_pk, construction_type, structure_type, structure_size, structure_unit).
        """
        try:
            for v in valuation_list:
                # normalize all fields
                c_type = v.get('Type') or v.get('type')
                s_type = v.get('Occupancy') or v.get('occupancy')
                size   = (int(v['Quantity']) if v.get('Quantity') not in (None, '') else None)
                unit   = v.get('Unit') or v.get('unit')
                cost   = self._parse_money(v.get('Unit Cost') or v.get('unit_cost'))
                value  = self._parse_money(v.get('Job Value') or v.get('job_value'))

                # lookup existing
                existing = (
                    self.session
                        .query(PermitValuation)
                        .filter_by(
                            permit_pk         = permit_pk,
                            construction_type = c_type,
                            structure_type    = s_type,
                            structure_size    = size,
                            structure_unit    = unit
                        )
                        .one_or_none()
                )

                if existing:
                    # update the numeric columns
                    existing.unit_cost_raw = cost
                    existing.job_value_raw = value
                    logger.debug(f"Updated valuation {existing.valuation_pk}")
                else:
                    # insert new
                    new = PermitValuation(
                        permit_pk         = permit_pk,
                        construction_type = c_type,
                        structure_type    = s_type,
                        structure_size    = size,
                        structure_unit    = unit,
                        unit_cost_raw     = cost,
                        job_value_raw     = value,
                    )
                    self.session.add(new)
                    logger.debug("Inserted new valuation")

            self.session.commit()

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"[PermitValuationExporter] upsert failed: {e}")
            raise

    def close(self):
        self.session.close()





class PermitProcessExporter:
    def __init__(self, db_connection):
        self.session = db_connection.get_session()

    def upsert(self, permit_pk: int, processing_info: list[dict]):
        """
        Upsert each record in processing_info into permit_process:
        match on (permit_pk, process_step, process_type, date_activated, date_marked).
     
        """
        # only these four steps
        allowed = {
            "Application Intake",
            "Review Consolidation",
            "Inspection",
            "Complete"
        }
        seen_keys = set()

        try:
            for rec in processing_info:
                step = rec.get("process_step")
                if step not in allowed:
                    continue

                raw_act = rec.get("activated_date")
                raw_mark = rec.get("marked_date")
                if not raw_act and not raw_mark:
                    continue

                # parse dates
                date_activated = (
                    parse_mmddyyyy(raw_act)
                    if isinstance(raw_act, str) and raw_act.strip()
                    else None
                )
                date_marked = (
                    parse_mmddyyyy(raw_mark)
                    if isinstance(raw_mark, str) and raw_mark.strip()
                    else None
                )

                # build a per‐row key to dedupe in this run
                key = (
                    permit_pk,
                    step,
                    rec.get("sub_step_type"),
                    date_activated,
                    date_marked
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                # natural‐key lookup
                existing = (
                    self.session.query(PermitProcess)
                    .filter_by(
                        permit_pk      = permit_pk,
                        process_step   = step,
                        process_type   = rec.get("sub_step_type"),
                        date_activated = date_activated,
                        date_marked    = date_marked
                    )
                    .one_or_none()
                )

                # prepare the mutable fields
                raw_comment = rec.get("comment")
                marked_comment = (
                    raw_comment.strip()
                    if isinstance(raw_comment, str)
                       and raw_comment.strip().upper() != "NULL"
                    else None
                )
                
                if existing:
                    existing.process_status = rec.get("status")
                    existing.marked_status  = rec.get("marked_status")
                    existing.marked_by      = rec.get("marked_by")
                    existing.marked_comment = marked_comment
                    logger.debug(f"Updated PermitProcess {existing.permit_process_pk}")
                else:
                    new = PermitProcess(
                        permit_pk       = permit_pk,
                        process_status  = rec.get("status"),
                        process_step    = step,
                        process_type    = rec.get("sub_step_type"),
                        marked_status   = rec.get("marked_status"),
                        marked_by       = rec.get("marked_by"),
                        marked_comment  = marked_comment,
                        date_activated  = date_activated,
                        date_marked     = date_marked,
                    )
                    self.session.add(new)
                    logger.debug("Inserted new PermitProcess record")

            # commit everything
            self.session.commit()

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"[PermitProcessExporter.upsert] failed: {e}")
            raise

    def close(self):
        self.session.close()




class PermitRelatedExporter:
    def __init__(self, db_connection):
        self.session = db_connection.get_session()

    def reconcile_related_pks(self):
        """
        Backfill any still-null related_permit_pk by matching
        related_full_permit_number → Permit.full_permit_number.
        """
        rows = (
            self.session
            .query(PermitRelated)
            .filter(PermitRelated.related_permit_pk.is_(None))
            .all()
        )
        for rel in rows:
            target = (
                self.session
                .query(Permit)
                .filter(Permit.full_permit_number == rel.related_full_permit_number)
                .first()
            )
            if target:
                rel.related_permit_pk = target.permit_pk

        self.session.commit()

    def upsert(
        self,
        permit_pk: int,
        full_permit_number: str,
        related_records: list[dict]
    ) -> list[PermitRelated]:
        """
        Upsert each related-record dict for this permit into permit_related.
        Match existing rows on (permit_pk, related_full_permit_number).
        """
        upserted = []
        try:
            for rec in related_records:
                rel_num = rec.get("Permit Number")
                # skip if blank or same as parent
                if not rel_num or rel_num == full_permit_number:
                    continue

                # parse date
                raw_date = rec.get("Date")
                related_date = None
                if isinstance(raw_date, str) and raw_date.strip().upper() not in ("", "NULL"):
                    related_date = parse_mmddyyyy(raw_date)

                # clean description
                raw_desc = rec.get("Project Name")
                related_description = (
                    raw_desc
                    if isinstance(raw_desc, str)
                    and raw_desc.strip()
                    and raw_desc.strip().upper() != "NULL"
                    else None
                )

                # natural‐key lookup
                existing = (
                    self.session
                    .query(PermitRelated)
                    .filter_by(
                        permit_pk                  = permit_pk,
                        related_full_permit_number = rel_num
                    )
                    .one_or_none()
                )

                if existing:
                    # UPDATE mutable fields
                    existing.related_permit_type        = rec.get("Permit Type")
                    existing.related_permit_description = related_description
                    existing.related_permit_date        = related_date
                    existing.related_permit_url         = rec.get("View Link") or None
                    logger.debug(f"Updated PermitRelated {existing.permit_related_pk}")
                    upserted.append(existing)
                else:
                    # INSERT new row
                    new = PermitRelated(
                        permit_pk                  = permit_pk,
                        full_permit_number         = full_permit_number,
                        related_permit_pk          = None,  # still to be reconciled
                        related_full_permit_number = rel_num,
                        related_permit_type        = rec.get("Permit Type"),
                        related_permit_description = related_description,
                        related_permit_date        = related_date,
                        related_permit_url         = rec.get("View Link") or None,
                    )
                    self.session.add(new)
                    upserted.append(new)
                    logger.debug("Inserted new PermitRelated")

            # commit all upserts at once
            self.session.commit()

            # refresh any newly inserted to populate PKs
            for row in upserted:
                self.session.refresh(row)

            return upserted

        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"[PermitRelatedExporter.upsert] {e}")
            raise

    def close(self):
        self.session.close()



class PermitConditionExporter:
    def __init__(self, db_connection):
        self.session = db_connection.get_session()

    def _normalize(self, raw: str | None) -> str | None:
        """Turn blank/whitespace into None, otherwise strip."""
        if raw is None:
            return None
        s = raw.strip()
        return s if s else None
    
    def upsert(self, permit_pk: int, conditions: list[dict]) -> list[PermitCondition]:
        """
        Upsert each condition for a given permit.
        Natural key: Match all fields EXCEPT status - status can be updated.
        """
        upserted = []
        try:
            full_num = (
                self.session
                    .query(Permit.full_permit_number)
                    .filter_by(permit_pk=permit_pk)
                    .scalar()
            ) or f"(pk={permit_pk})"

       
            for i, cond in enumerate(conditions):
              
                # Process date
                raw_date = cond.get("condition_date")
                date_updated = None
                if raw_date and str(raw_date).strip().upper() not in ("", "NULL"):
                    date_updated = parse_mmddyyyy(raw_date)
                
                # Get all values exactly as scraped
                final_group       = self._normalize(cond.get("condition_group_info"))
                final_type_code   = self._normalize(cond.get("condition_type_code"))
                final_type        = self._normalize(cond.get("condition_type"))
                final_title       = self._normalize(cond.get("condition_title"))
                final_description = self._normalize(cond.get("condition_description"))
                final_status      = self._normalize(cond.get("condition_status"))
                
                try:
                    # Match ROW - all fields EXCEPT status
                    query = self.session.query(PermitCondition).filter(
                        PermitCondition.permit_pk == permit_pk,
                        PermitCondition.condition_type == final_type,
                        PermitCondition.condition_title == final_title,
                        PermitCondition.condition_description == final_description
                        # NOTE: condition_status is EXCLUDED from matching
                    )
                    
                    # Handle NULL values properly
                    if final_group is not None:
                        query = query.filter(PermitCondition.condition_group == final_group)
                    else:
                        query = query.filter(PermitCondition.condition_group.is_(None))
                    
                    if final_type_code is not None:
                        query = query.filter(PermitCondition.condition_type_code == final_type_code)
                    else:
                        query = query.filter(PermitCondition.condition_type_code.is_(None))
                    
                    if date_updated is not None:
                        query = query.filter(PermitCondition.date_updated == date_updated)
                    else:
                        query = query.filter(PermitCondition.date_updated.is_(None))
                    
                    existing = query.one_or_none()
                    
                except MultipleResultsFound:
                    existing = query.order_by(PermitCondition.permit_condition_pk).first()

                if existing:
                    # Found matching condition - UPDATE the status (and other fields if needed)
                    old_status = existing.condition_status
                    
                    # Update all mutable fields
                    existing.condition_status = final_status
                    existing.condition_type = final_type
                    existing.condition_title = final_title
                    existing.condition_description = final_description
                    # Note: We don't update the natural key fields (group, type_code, date)

                    upserted.append(existing)
                else:
                    # No match found - create new condition

                    new = PermitCondition(
                        permit_pk             = permit_pk,
                        condition_group       = final_group,
                        condition_type        = final_type,
                        condition_type_code   = final_type_code,
                        condition_title       = final_title,
                        condition_description = final_description,
                        condition_status      = final_status,
                        date_updated          = date_updated,
                    )
                    self.session.add(new)
                    upserted.append(new)

          
            self.session.commit()
            
            for pc in upserted:
                self.session.refresh(pc)
            return upserted

        except SQLAlchemyError as e:
            self.session.rollback()
            raise

    def close(self):
        self.session.close()