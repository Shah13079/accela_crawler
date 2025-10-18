import re
import os, json
import logging
import pandas as pd
from pathlib import Path
from scrapy.selector import Selector
from playwright.async_api import Page
from datetime import datetime, timedelta



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        #This is to show output in console
        logging.StreamHandler(),  
        # logging.FileHandler('scraper.log') 
    ])

logger = logging.getLogger(__name__)

async def select_dropdown_by_visible_text(page: Page, element_id: str, visible_text: str, wait_time: int = 2000):
    """
    Select an option from a dropdown by its visible text using Playwright.
    
    Args:
        page: Playwright page object
        element_id: ID of the dropdown element
        visible_text: The visible text of the option to select
        wait_time: Time to wait after selection in milliseconds (default: 10000)
    """
    # Wait for the element to be available
    await page.wait_for_selector(f'#{element_id}', state='visible')
    # Select the option by visible text
    await page.select_option(f'#{element_id}', label=visible_text)
    # Wait after selection
    await page.wait_for_timeout(wait_time)
    logger.info(f"Selected dropdown option '{visible_text}' and waited {wait_time/1000} seconds")


def get_date_range(config_path='config.json'):
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    days = config.get('date_range_days', 30)
    today = datetime.date.today()
    start_date = today - timedelta(days=days)
    return start_date.strftime('%m/%d/%Y'), today.strftime('%m/%d/%Y')


async def click_element(page: Page, element_id: str, wait_time: int = 2000):
    """
    Click an element by its ID using JavaScript execution in Playwright.
    
    Args:
        page: Playwright page object
        element_id: ID of the element to click
        wait_time: Time to wait after clicking in milliseconds (default: 2000)
        
    Returns:
        page: The page object for chaining
    """
    # Wait for the element to be clickable
    await page.wait_for_selector(f'#{element_id}', state='visible')
    
    # Click the element using JavaScript (similar to Selenium's execute_script)
    await page.evaluate(f'document.getElementById("{element_id}").click()')
    
    # Wait after clicking
    await page.wait_for_timeout(wait_time)
    logger.info(f"Clicked element '{element_id}' and waited {wait_time/1000} seconds")
    return page


async def put_date(page: Page, element_id: str, date_str: str, clear_wait: int = 1000, type_wait: int = 1000):
    """
    Clear a date field and enter a new date.
    
    Args:
        page: Playwright page object
        element_id: ID of the element to input date into
        date_str: The date string to enter
        clear_wait: Time to wait after clearing in milliseconds (default: 1000)
        type_wait: Time to wait after typing in milliseconds (default: 1000)
    """
    # Focus on the element first to ensure we're typing in the right field
    await page.focus(f'#{element_id}')
    # Clear existing text (select all)
    await page.keyboard.press('Control+a')
    await page.wait_for_timeout(500)
    # Delete the selected text
    await page.keyboard.press('Delete')
    await page.wait_for_timeout(clear_wait)
    # Type the new date
    await page.keyboard.type(date_str)
    # Wait after typing
    await page.wait_for_timeout(type_wait)
    # Press Tab to exit the field
    await page.keyboard.press('Tab')
    await page.wait_for_timeout(1000)
    
    logger.info(f"Input date '{date_str}' into element '{element_id}'")
    return page

# Write header only once if file doesn't exist
def write_row_to_csv(row_data, output_file = None):
    df = pd.DataFrame([row_data])
    write_header = not os.path.isfile(output_file)
    df.to_csv(output_file, mode='a', header=write_header, index=False)

#HELPER FUNCTIONS FOR PARSING Permit DETAILS 
def is_address_line(line):
    street_suffixes = [
        "ST", "AVE", "AVENUE", "BLVD", "RD", "ROAD", "DR", "DRIVE", "CT", "LN", "LANE", 
        "PKWY", "PL", "WAY", "HWY", "TERR", "EXPRESSWAY", "TRAIL", "CIR", "LOOP",
        "E.", "W.", "N.", "S.", "SUITE", "STE", "UNIT", "FLOOR", "APT"
    ]
    suffix_pattern = re.compile(r'\b(' + '|'.join(street_suffixes) + r')\b', re.IGNORECASE)
    
    # Use word boundaries to check for whole words only
    exclude_pattern = re.compile(r'\b(phone|contractor|mt|id|zip|fax|wa|nd|sd)\b', re.IGNORECASE)

    stripped = line.strip()

    # Exclude obvious non-address lines (checking for whole words)
    if exclude_pattern.search(stripped.lower()):
        return ''

    # Include if line has address suffix keyword and at least one digit
    if suffix_pattern.search(stripped) and re.search(r'\d', stripped):
        return stripped

    return ''


# this function is using by license_pro_info
def extract_city_state_zip(line):
    """
    Extract city, state, and zip (if any) from a single line.
    Returns dict with keys if found, else empty string for missing parts.
    Returns empty dict if no match.
    """

    line = line.strip()

    # US state abbreviations
    states = [
        'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL',
        'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT',
        'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI',
        'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    ]
    states_regex = '|'.join(states)

    # Regex to capture city, state, zip (zip optional)
    # Accept commas or spaces as separators
    pattern = re.compile(
        rf"""
        ^\s*
        (?P<city>[\w\s\.\'\-]+?)    # city - lazy match, words/spaces/dots/quotes/hyphens
        [, ]+                       # separator (comma or space, one or more)
        (?P<state>{states_regex})   # state abbreviation
        (?:[, ]+\s*(?P<zip>\d{{5}}(?:-\d{{4}})?))?  # optional zip code with optional +4
        \s*$
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    match = pattern.match(line)
    if not match:
        return {}

    city = match.group('city').strip()
    state = match.group('state').upper()
    zip_code = match.group('zip') or ''

    return {
        'license_pro_city': city,
        'license_pro_state': state,
        'license_pro_zip': zip_code
    }

# this function is using by license_pro_info to detect license code
def extract_business_license(line):
    """
    Extract the license code from lines starting with any uppercase label,
    e.g. "CONTRACTOR 2015-MSS-CON-00062" or "LICENSE 1234-XYZ".
    Returns the code string only, or '' if no match.
    """
    pattern = re.compile(r'^([A-Z]+)\s+([\w\-]+)', re.IGNORECASE)
    match = pattern.match(line.strip())
    if match:
        # match.group(1) is the label (e.g., CONTRACTOR)
        # match.group(2) is the license/code part
        return match.group(2)
    return ''

async def safe_element_exists(page, xpath):
    try:
        return await page.locator(xpath).count() > 0
    except:
        return False

async def safe_get_html(page, xpath):
    try:
        element = page.locator(xpath).first
        if await element.count() > 0:
            return await element.inner_html()
    except:
        pass
    return ""



# detects po_box address line
def extract_po_box(line):
    """
    Detects if the line is a PO BOX address.
    Returns the PO BOX string (e.g., "PO BOX 1951") if matched, else ''.
    """
    po_box_pattern = r'\b(?:P\.?\s*O\.?|POST\s+OFFICE)\s+BOX\s+\d+(?:-\d+)?\b'
    
    match = re.search(po_box_pattern, line, re.IGNORECASE)
    return match.group(0) if match else ''

# Parsing data for Licensed Professional
def license_pro_info(html_content):
    html_content = Selector(text= html_content)
    professional_text_details = html_content.xpath(
        "(.//td)[2]//text()[not(ancestor::table[@class='ACA_TDAlignLeftOrRightTop'])]"
    ).getall()

    professional_details = [item.strip() for item in professional_text_details if item.strip() and item.strip() != '*' and 'Phone' not in item]
    
    filtered = [
    s for s in professional_details
    if not re.match(r'^BL\d+$', s.strip()) ]
        
    license_p_details = {
    'license_pro_business_name': '',
    'license_pro_address_line': '',
    'license_pro_city': '',
    'license_pro_state': '',
    'license_pro_zip': '',
    'license_pro_business_license': '',
    'license_pro_po_box': '',
    'license_pro_phone_num_1': '',
    'license_pro_phone_num_2':'',
    'license_pro_phone_num_3' :''
     }

    for idx, each_line in enumerate(filtered+[' '], start=1):
        if idx ==1:
            license_p_details['license_pro_business_name'] = each_line
            continue

        po_box = extract_po_box(each_line)
        if po_box:
            license_p_details['license_pro_po_box'] = po_box
            continue

        address_line = is_address_line(each_line)
        if address_line:
            license_p_details['license_pro_address_line'] = address_line
            continue
        
        city_state_zip = extract_city_state_zip(each_line)
        if city_state_zip:
            license_p_details.update(city_state_zip)
            continue

        license_code = extract_business_license(each_line)
        if license_code:
            license_p_details['license_pro_business_license'] = license_code
            continue

        phone_numbers = html_content.xpath('//div[@class="ACA_PhoneNumberLTR"]/text()').getall()
        clean_phones = (item.strip() for item in phone_numbers if item.strip())
        for ind,each_num in enumerate(clean_phones,start=1):
            license_p_details.update({f"license_pro_phone_num_{ind}": each_num})
    
    return license_p_details



# Extracting ownner section information dynamically

def extract_city_state_zip_owner(line):
    # Initialize empty result dictionary with all possible fields
    result = {
        'owner_city': None,
        'owner_state': None,
        'owner_zipcode': None,
        'owner_unit': None
    }
    
    # Clean the input
    line = line.strip()
    
    # Pattern to match: City name + state code + zip code + optional unit
    # Group 1: City (one or more words before the state code)
    # Group 2: State code (2 uppercase letters)
    # Group 3: ZIP code (5 digits)
    # Group 4: Optional unit number (typically 3 digits)
    pattern = r'([A-Za-z\s]+)\s+([A-Z]{2})\s+(\d{5})(?:\s+(\d{3}))?'
    
    match = re.match(pattern, line)
    
    if match:
        # Extract the components
        city, state, zipcode, unit = match.groups()
        
        # Update the result dictionary
        result['owner_city'] = city.strip()
        result['owner_state'] = state
        result['owner_zipcode'] = zipcode
        result['owner_unit'] = unit  # Will be None if not present
        
        return result
    
    # Alternative pattern that's more flexible with spacing and punctuation
    alt_pattern = r'([A-Za-z\s]+?)[,\s]+([A-Z]{2})[,\s]+(\d{5}(?:-\d{4})?)(?:[,\s]+(\d{3}))?'
    
    alt_match = re.search(alt_pattern, line)
    
    if alt_match:
        # Extract the components
        city, state, zipcode, unit = alt_match.groups()
        
        # Update the result dictionary
        result['owner_city'] = city.strip()
        result['owner_state'] = state
        result['owner_zipcode'] = zipcode
        result['owner_unit'] = unit  # Will be None if not present
        
        return result
    
    return result


def is_mail_to_line(line):
     return "MAIL TO:" in line

def extract_email(line):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_pattern, line)
    # Return the matched email if found, None otherwise
    return match.group(0) if match else None

def extract_owner_info(owner_html):
    
    owner_source = Selector(text= owner_html)
    # owner_title = owner_source.xpath('//span[contains(text(),"*")]/parent::node()/text()').get()
    owner_all_text = owner_source.xpath('//td/text()').getall()
    clean_lines = [item.strip() for item in owner_all_text if item]
    
    owner_details = {}
    for idx, line in enumerate(clean_lines + [" "] , start=1):
        if idx == 1:
            owner_details["owner_business"] = line
        
        
        mail_to = is_mail_to_line(line)
        if mail_to:
            owner_details["owner_mail_to"] = line.split(":")[1].strip()
            continue

        owner_email = extract_email(line)
        if owner_email:
            owner_details["owner_email"] = owner_email
            continue
            
        if is_address_line(line):
            owner_details["owner_address_line"] = line
            continue

        po_box = extract_po_box(line)
        if po_box:
            owner_details["owner_po_box"] = po_box
            continue

        if line.strip():
            result = extract_city_state_zip_owner(line)
            if result['owner_city'] and result['owner_state'] is not None:
                owner_details.update(result)
                continue

        phone_numbers = owner_source.xpath('//div[@class="ACA_PhoneNumberLTR"]/text()').getall()
        clean_phones = (item.strip() for item in phone_numbers if item.strip())
        for ind,each_num in enumerate(clean_phones,start=1):
            owner_details.update({f"owner_phone_num_{ind}": each_num})

    return owner_details





def ext_application_info(app_info_html):
    app_info_source = Selector(text=app_info_html)
    
    # All possible fields grouped and ordered by section
    ordered_fields = {
        "PROJECT INFORMATION": [
            "job_cost_valuation", "structure_demolition", "repair", "addition", "reroof", "reside", "remodel", 
            "tenant_improvement", "change_of_use", "zcp_required", "drywell_or_sump", "visitability_resolution_applicable", "project_cost"
        ],
        "BUILDING INFORMATION": [
            "slab", "crawl_space", "basement", "shell_only", "roof_pitch"
        ],
        "BUILDING DETAILS": [
            "construction_type_code_1", "occupancy_type_code", "residential_construction_type_code_1",
            "residential_occupancy_type_1", "number_of_stories", "number_of_dwelling_units",
            "smoke_detector_required", "sprinklers_required"
        ],
        "PROPERTY INFORMATION": [
            "property_square_feet", "total_sf_after_addition"
        ],
        "SUB PLANS SUBMITTED": [
            "water_meter_/_line_size", "water_supply", "heating_source", "other", "other_title"
        ],
        "HISTORICAL": [
            "commercial_subtype", "residential_subtype"
        ],
        "STORMWATER PROJECT INFORMATION": [
            "swppp_coverage_permit", "disturbed_area"
        ],
        "OTHER": [] 
    }

    # Flatten all keys into one list for easy lookup
    all_possible_keys = [key for section in ordered_fields.values() for key in section]

    # Initialize the field_data with all keys set to ''
    field_data = {key: '' for key in all_possible_keys}

    # Extract all labels and values
    labels = app_info_source.xpath(
        './/div[contains(@class, "MoreDetail_ItemColASI") and contains(@class, "MoreDetail_ItemCol1")]/span/text()'
    ).getall()

    values = app_info_source.xpath(
        './/div[contains(@class, "MoreDetail_ItemColASI") and contains(@class, "MoreDetail_ItemCol2")]/span/text()'
    ).getall()

    # Normalize keys (strip colons, spaces -> underscores, lowercase)
    for label, value in zip(labels, values):
        clean_label = label.replace(':', '').strip().lower().replace(' ', '_')
        if clean_label in field_data:
            field_data[clean_label] = value.strip()
        else:
            field_data[clean_label] = value.strip()  

    return field_data

def clean_parcel_number(raw: str) -> str | None:
    """
    Take something like:
      "0) 04219902101010000"
      "0) Parcel Number:04220008202010000"
      "04220021130010000"
    and return the 17-char code, or None if we can’t find one.
    """
    if not raw:
        return None

    # 1) Strip any leading numbering like "0) "
    s = re.sub(r'^\s*\d+\)\s*', '', raw)

    # 2) Remove the literal label if still present
    s = s.replace('Parcel Number:', '').strip()

    # 3) Extract the first 17-character alphanumeric chunk
    m = re.search(r'([A-Z0-9]{17})', s)
    if m:
        return m.group(1)

    # 4) Fallback: if it's all digits and length==17, return that
    digits = re.sub(r'\D', '', s)
    return digits if len(digits) == 17 else None


def extract_parcel_info(html):
    sel = Selector(text=html)
    parcel_info = {"parcel_number":"",
                   "parcel_block":"",
                   "parcel_lot":"",
                   "parcel_subdivision":""
                   }

    # Parcel Number
    parcel_number_raw = sel.xpath('//div[contains(text(), "Parcel Number:")]/text()').get()
    if parcel_number_raw:
        parcel_info['parcel_number'] = clean_parcel_number(parcel_number_raw.replace('Parcel Number:', '').strip())

    # Block
    block_raw = sel.xpath('//div[contains(text(), "Block:")]/text()').get()
    if block_raw:
        parcel_info['parcel_block'] = block_raw.replace('Block:', '').strip()

    # Lot
    lot_raw = sel.xpath('//div[contains(text(), "Lot:")]/text()').get()
    if lot_raw:
        parcel_info['parcel_lot'] = lot_raw.replace('Lot:', '').strip()

    # Subdivision
    subdivision_raw = sel.xpath('//div[contains(text(), "Subdivision:")]/text()').get()
    if subdivision_raw:
        parcel_info['parcel_subdivision'] = subdivision_raw.replace('Subdivision:', '').strip()

    return parcel_info


def extract_table_list_info(html: str) -> dict:
    sel = Selector(text=html)
    data = {}

    # This selects all label-value blocks in the main content area
    items = sel.xpath('//div[contains(@class, "MoreDetail_Item")]/div')
    
    # We loop pairwise: label div then value div
    for i in range(0, len(items), 2):
        label = items[i].xpath('normalize-space(span/text())').get()
        value = items[i+1].xpath('normalize-space(span/text())').get()

        if label:
            key_clean = label.strip().lower().replace(" ", "_").replace(":", "")
            data[key_clean] = value.strip() if value else ""

    return data


# Extracts Related contacts in dynamic way no matter how much blocks are there
def normalize_label(text):
    """Convert heading like 'Business Owner Information' → 'business_owner'"""
    text = re.sub(r'information$', '', text.strip(), flags=re.IGNORECASE)
    return re.sub(r'\W+', '_', text.strip().lower()).strip('_')

def extract_contact_info_blocks(html: str) -> list:
    selector = Selector(text=html)
    contact_blocks = selector.xpath('//td[@class="ACA_Table_Align_Top"]')
    contact_dicts = []

    for block in contact_blocks:
        # Get section label (e.g., Business Owner Information → business_owner)
        section_title = block.xpath('.//h2/text()').get(default="").strip()
        if not section_title:
            continue
        section_key = normalize_label(section_title)

        contact_info = {}
        contact_info['which_source_prefix'] = section_key

        # Basic fields
        firstname = block.xpath('.//span[contains(@class,"contactinfo_firstname")]/text()').get(default='').strip()
        lastname = block.xpath('.//span[contains(@class,"contactinfo_lastname")]/text()').get(default='').strip()
        business_name = block.xpath('.//span[contains(@class,"contactinfo_businessname")]/text()').get(default='').strip()
        address_line3 = block.xpath('.//span[contains(@class,"contactinfo_addressline3")]/text()').get(default='').strip()
        region = block.xpath('.//span[contains(@class,"contactinfo_region")]/text()').get(default='').strip()

        phone1 = block.xpath('.//span[contains(@class,"contactinfo_phone1")]//div/text()').get(default='').strip()
        phone2 = block.xpath('.//span[contains(@class,"contactinfo_phone2")]//div/text()').get(default='').strip()

        email = block.xpath('.//span[contains(@class,"contactinfo_email")]//td[last()]/text()').get(default='').strip()

      
        if firstname:
            contact_info[f"{section_key}_first_name"] = firstname
        if lastname:
            contact_info[f"{section_key}_last_name"] = lastname
        if business_name:
            contact_info[f"{section_key}_business_name"] = business_name
        if address_line3:
            contact_info[f"{section_key}_address"] = address_line3
        if region:
            contact_info[f"{section_key}_region"] = region
        if phone1:
            contact_info[f"{section_key}_phone1"] = phone1
        if phone2:
            contact_info[f"{section_key}_phone2"] = phone2
        if email:
            contact_info[f"{section_key}_email"] = email

        contact_dicts.append(contact_info)

    return contact_dicts

# Parsing conditions per page
def parse_conditions(html: str):
    sel = Selector(text=html)
    condition_rows = []

    for td in sel.xpath('//table[@id="ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList"]//td[contains(@class, "ACA_AlignLeftOrRightTop")]'):
        row = {}

        # Group name and count 
        group_name = td.xpath('.//div[contains(@id, "_divGeneralConditionsGroupName")]/span[1]/text()').get()
        group_count = td.xpath('.//div[contains(@id, "_divGeneralConditionsGroupName")]/span[2]/text()').get()
        if group_name or group_count:
            row["condition_group_info"] = f"{(group_name or '').strip()} {(group_count or '').strip()}".strip()

        # Type code 
        type_code = td.xpath('.//div[contains(@id, "_divGeneralConditionsType")]/span/text()').get()
        if type_code:
            row["condition_type_code"] = type_code.strip()

        # Condition title
        condition_title = td.xpath('.//span[contains(@id, "_lblGeneralConditionsInfo")]/div[1]/text()').get()
        if condition_title:
            row["condition_title"] = condition_title.strip()

        # Condition description 
        description = td.xpath('.//span[contains(@id, "_lblGeneralConditionsInfo")]/div[2]/text()').get()
        if description:
            row["condition_description"] = description.strip()

        # Status line
        status_line = td.xpath('.//span[contains(@id, "_lblGeneralConditionsInfo")]/div[3]/text()').get()
        if status_line:
            parts = [p.strip() for p in status_line.split('|')]
            if len(parts) == 3:
                row["condition_status"] = parts[0]
                row["condition_type"] = parts[1]
                try:
                    date_obj = datetime.strptime(parts[2], "%m/%d/%Y")
                    row["condition_date"] = date_obj.strftime("%Y-%m-%d")
                except ValueError:
                    row["condition_date"] = parts[2]  
            else:
                row["condition_status_line"] = status_line.strip()
        condition_rows.append(row)
    return condition_rows
        


def parse_inspections(html_content):
    inspections = []
    response = Selector(text=html_content)
    import re
    from datetime import datetime

    # Parse completed inspections
    completed_rows = response.xpath('//div[@id="ctl00_PlaceHolderMain_InspectionList_completedPanel"]//tr[contains(@class, "InspectionListRow")]')
    
    for row in completed_rows:
        # Get all text from the row
        all_text = row.xpath('.//text()').getall()
        full_text = ' '.join([t.strip() for t in all_text if t.strip()])
        
        # Initialize variables
        status = title = result_by = date = time = ''
        
       
        # Status is in the bold span
        status_elem = row.xpath('.//span[@style and contains(@style, "font-weight: bold")]/text()').get()
        if status_elem:
            status = status_elem.strip()
        
        # Title is in the span that comes after the bold span (usually font-size: 1.2em)
        title_elem = row.xpath('.//span[@style and contains(@style, "font-size: 1.2em")]/text()').get()
        if title_elem:
            title = title_elem.strip()
        
       
    
        # Extract inspector and date/time using comprehensive patterns
        inspector_date_patterns = [
            # Standard patterns with "Result by" or "Cancelled by"
            r'Result by:\s*([^,\n]+?)(?:\s+on\s+|\s+)(\d{1,2}/\d{1,2}/\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)',
            r'Cancelled by:\s*([^,\n]+?)(?:\s+on\s+|\s+)(\d{1,2}/\d{1,2}/\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)',
            
            # More flexible patterns
            r'Result by:\s*([^\d]+?)\s+(\d{1,2}/\d{1,2}/\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)',
            r'Cancelled by:\s*([^\d]+?)\s+(\d{1,2}/\d{1,2}/\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)',
            
            # Just date and time (no inspector)
            r'(\d{1,2}/\d{1,2}/\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)',
        ]
        
        for pattern in inspector_date_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 3:  # Inspector, date, time
                    result_by = groups[0].strip()
                    date_str = groups[1].strip()
                    time = groups[2].strip()
                elif len(groups) == 2:  # Just date, time
                    date_str = groups[0].strip()
                    time = groups[1].strip()
                
                # Convert date format
                try:
                    date = datetime.strptime(date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
                except:
                    pass
                break
        
        # Clean up result_by
        if result_by:
            # Remove common prefixes
            result_by = re.sub(r'Result by:\s*|Cancelled by:\s*', '', result_by, flags=re.IGNORECASE)
            result_by = result_by.strip()
            
            # Handle "unassigned" case
            if result_by.lower() == 'unassigned':
                result_by = 'unassigned'
            elif not result_by or result_by.lower() in ['', 'none']:
                result_by = None
        else:
            result_by = None


        inspections.append({
            'inspection_section': 'Completed',
            'status': status,
            'title': title,
            'result_by': result_by,
            'date': date,
            'time': time
        })

  

    # Parse upcoming inspections
    upcoming_rows = response.xpath('//table[@id="ctl00_PlaceHolderMain_InspectionList_gvListUpcoming"]//tr[contains(@class, "InspectionListRow")]')
    
    for row in upcoming_rows:
        cell = row.xpath('.//td[contains(@class, "ACA_AlignLeftOrRightTop")]')
        spans = cell.xpath('.//span/text()').getall()
        spans = [s.strip().replace(u'\xa0', ' ').strip() for s in spans if s.strip()]

        date = title = status = result_by = ''
        
        try:
            if len(spans) >= 3:
                date = datetime.strptime(spans[0], "%m/%d/%Y").strftime("%Y-%m-%d")
                title = spans[1]
                status = spans[2]
            
            # Extract inspector information
            if len(spans) >= 4 and spans[3].startswith('Inspector:'):
                # Try xpath approach first
                inspector_elem = cell.xpath('.//span[contains(text(), "Inspector:")]/i/text()').get()
                if inspector_elem:
                    result_by = inspector_elem.strip()
                else:
                    # Fallback to text parsing
                    result_by = spans[3].replace('Inspector:', '').strip()
                    
                # Handle "unassigned" case
                if result_by and result_by.lower() == 'unassigned':
                    result_by = 'unassigned'
                elif not result_by or result_by.lower() in ['', 'none']:
                    result_by = None
                    
        except Exception as e:
            pass
        inspections.append({
            'inspection_section': 'Upcoming',
            'status': status,
            'title': title,
            'result_by': result_by,
            'date': date,
            'time': ''
        })

    return inspections

# parse valuation table 
def parse_valuation_table(html_content):
    selector = Selector(text=html_content)

    valuation_table = selector.xpath("//table[contains(@id, 'gdvValuationCalculatorList')]")

    # Extract column names
    column_names = valuation_table.xpath(".//tr[contains(@class, 'ACA_TabRow_Header')]//th//span/text()").getall()
    column_names = [name.strip() for name in column_names if name.strip()]

    # Extract data rows - include both odd and even rows
    data_rows = []
    for row in valuation_table.xpath(".//tr[contains(@class, 'ACA_TabRow_Odd') or contains(@class, 'ACA_TabRow_Even')]"):
        cells = row.xpath(".//td//span/text()").getall()
        cells = [cell.strip() for cell in cells if cell.strip()]
        row_data = dict(zip(column_names, cells))
        data_rows.append(row_data)

    return data_rows

#Parse related records table
def parse_related_records_table(html_content):
    # Create selector from the HTML content
    if isinstance(html_content, str):
        selector = Selector(text=html_content)
    else:
        selector = html_content
    
    # Select rows with names starting with '_'
    rows = selector.xpath("//table[@id='tableCapTreeList']//tr[starts-with(@name, '_')]")
    
    related_records = []
    for row in rows:
        permit_number = row.xpath(".//td[1]//table//tr/td[last()]/text()").get()
        
        # Permit type is in the 2nd td
        permit_type = row.xpath("./td[2]/text()").get()
        
        # Project name is in the 3rd td
        project_name = row.xpath("./td[3]/text()").get()
        
        # Date is inside a div in the 4th td
        date = row.xpath("./td[4]//div/text()").get()
        
        # Link is inside the anchor tag in the 5th td
        view_href = row.xpath("./td[5]//a/@href").get()
        if view_href and 'https://' not in view_href:
            view_href = "https://aca-prod.accela.com/MISSOULA/" + view_href.lstrip("../")
          

        record = {
            "Permit Number": permit_number.strip() if permit_number else "",
            "Permit Type": permit_type.strip() if permit_type else "",
            "Project Name": project_name.strip() if project_name else "",
            "Date": date.strip() if date else "",
            "View Link": view_href.strip() if view_href else ""
        }
        related_records.append(record)

    return related_records



def parse_process_info(html_content: str ):
   
    
    sel = Selector(text=html_content)
    rows = []
    
    headers = [
        "process_step", "status", "sub_step_type", "activated_date", "assigned_to",
        "marked_status", "marked_date", "marked_by", "comment"
    ]
    
    main_steps = sel.xpath('//tr[contains(@class, "ACA_TabRow_") and ./td[@width="770px"]]')
    
    for step in main_steps:
        step_name = step.xpath('./td[@width="770px"]/text()').get()
        if not step_name or not step_name.strip():
            continue
        
        status_img = step.xpath('.//img[contains(@title, "complete") or contains(@title, "active")]/@title').get()
        status = status_img.capitalize() if status_img else "Unknown"
        
        rows.append({
            "process_step": step_name.strip(),
            "status": status,
            "sub_step_type": "Main",
            "activated_date": "",
            "assigned_to": "",
            "marked_status": "",
            "marked_date": "",
            "marked_by": "",
            "comment": ""
        })
        
        step_id = step.xpath('./@id').get()
        if not step_id:
            onclick = step.xpath('.//a[contains(@onclick, "ControlDisplay")]/@onclick').get() or ""
            match = re.search(r'\$get\("([^"]+)"\)', onclick)
            if match:
                step_id = match.group(1)
        
        if step_id:
            # Find the detail section (whether it's currently displayed or not)
            detail_section = sel.xpath(f'//tr[@id="{step_id}"]')
            
            if detail_section:
                info_tables = detail_section.xpath('.//table[contains(@role, "presentation")]')
                
                for table in info_tables:
                    # Look for rows that contain activation/status info
                    status_rows = table.xpath('.//tr[contains(@class, "ACA_TabRow_Bold") or contains(@class, "ACA_TabRow_Italic")]')
                    
                    for status_row in status_rows:
                        # Determine row type
                        row_class = status_row.xpath('./@class').get() or ""
                        sub_step_type = "Bold" if "ACA_TabRow_Bold" in row_class else "Italic"
                        
                        # Find the cell with the status text
                        status_cell = status_row.xpath('.//td[contains(@class, "ACA_ALeft")]//td[contains(text(), "Activated on")]')
                        if not status_cell:
                            continue
                        
                        # Extract all the spans with the data we need
                        spans = status_cell.xpath('.//span/text()').getall()
                        
                        # Initialize variables
                        activated_date = ""
                        assigned_to = ""
                        marked_status = ""
                        marked_date = ""
                        marked_by = ""
                        
                        # Find values by scanning the text and spans
                        cell_text = status_cell.xpath('string(.)').get() or ""
                        
                        # Find activated date (first span after "Activated on")
                        activated_match = re.search(r'Activated on ([^,]+)', cell_text)
                        if activated_match and len(spans) > 0:
                            activated_date = spans[0]
                        
                        # Find assigned to (first span after "assigned to")
                        assigned_match = re.search(r'assigned to ([^\n]+)', cell_text)
                        if assigned_match and len(spans) > 1:
                            assigned_to = spans[1]
                        
                        # Find marked status (first span after "Marked as")
                        marked_match = re.search(r'Marked as ([^on]+)', cell_text)
                        if marked_match and len(spans) > 2:
                            marked_status = spans[2]
                        
                        # Find marked date (first span after "on" that follows "Marked as")
                        if "Marked as" in cell_text and "on" in cell_text and len(spans) > 3:
                            marked_date = spans[3]
                        
                        # Find marked by (first span after "by")
                        if "by" in cell_text and len(spans) > 4:
                            marked_by = spans[4]
                        
                        # Look for comment - FIXED COMMENT EXTRACTION
                        comment = ""
                        # Try to find comment ID from the onclick attribute
                        comment_link = status_row.xpath('.//a[contains(@onclick, "ControlDisplay")]')
                        if comment_link:
                            onclick = comment_link.xpath('./@onclick').get() or ""
                            match = re.search(r'\$get\("([^"]+)"\)', onclick)
                            if match:
                                comment_id = match.group(1)
                                comment_row = sel.xpath(f'//tr[@id="{comment_id}"]')
                                if comment_row:
                                    # Try multiple approaches to extract the comment
                                    
                                    # Approach 1: Navigate through the nested table structure
                                    comment = comment_row.xpath('.//td//span[@class="ACA_Comments"]/parent::td/following-sibling::td[2]/span/text()').get()
                                    
                                    # Approach 2: More direct approach using the table structure
                                    if not comment:
                                        comment = comment_row.xpath('.//table[@role="presentation"]//tr/td[3]/span/text()').get()
                                    
                                    # Approach 3: Find any span that doesn't have the ACA_Comments class
                                    if not comment:
                                        non_header_spans = comment_row.xpath('.//span[not(contains(@class, "ACA_Comments"))]/text()').getall()
                                        if non_header_spans:
                                            comment = non_header_spans[0]
                        
                        # Add this sub-step to our rows
                        rows.append({
                            "process_step": step_name.strip(),
                            "status": status,
                            "sub_step_type": sub_step_type,
                            "activated_date": activated_date.strip() if activated_date else "",
                            "assigned_to": assigned_to.strip() if assigned_to else "",
                            "marked_status": marked_status.strip() if marked_status else "",
                            "marked_date": marked_date.strip() if marked_date else "",
                            "marked_by": marked_by.strip() if marked_by else "",
                            "comment": comment.strip() if comment else ""
                        })
    
    
    return rows



def parse_formate_address(address_full):
    """
    Parse actual address formats like:
    - "2305 BENTON AVE, MISSOULA MT 59801"
    - "283 W FRONT ST, SHELL, MISSOULA MT 59802"
    
    And structure according to client's desired format:
    "{street_number} {street_name} {street_type}, {street_unit}, {city}, {state} {postal_code}"
    """
    components = {
        'street_number': None,
        'street_name': None,
        'street_type': None,
        'street_unit': None,
        'city': 'MISSOULA',  # Default
        'state': 'MT',       # Default
        'postal_code': None
    }
    
    if not address_full:
        return components
    

    
    # Split by commas
    parts = [part.strip() for part in address_full.split(',')]
    
    # Process the last part (city, state, zip)
    if parts:
        last_part = parts[-1]
        words = last_part.split()
        
        # Check if we have at least 3 words (city, state, zip)
        if len(words) >= 3:
            # Last word is zip code
            components['postal_code'] = words[-1]
            # Second-to-last word is state
            components['state'] = words[-2]
            # All previous words form the city
            components['city'] = ' '.join(words[:-2])
    
    # Process the first part (street number, name, type)
    if parts:
        street_info = parts[0].split()
        
        # First element is street number
        if street_info and street_info[0].isdigit():
            components['street_number'] = street_info[0]
            
            # Last element is street type
            if len(street_info) > 2:
                components['street_type'] = street_info[-1]
                
                # Middle elements form street name
                components['street_name'] = ' '.join(street_info[1:-1])
            elif len(street_info) == 2:
                # Only two elements: number and name
                components['street_name'] = street_info[1]
    
    # Process middle parts as unit info
    if len(parts) > 2:
        # All parts between first and last are unit info
        components['street_unit'] = ', '.join(parts[1:-1])
    
    return components


def format_address_for_client(components):
    """Format address components according to client's desired format"""
    address_parts = []
    
    # Street part: "{street_number} {street_name} {street_type}"
    street_part = []
    if components['street_number']:
        street_part.append(components['street_number'])
    if components['street_name']:
        street_part.append(components['street_name'])
    if components['street_type']:
        street_part.append(components['street_type'])
    
    if street_part:
        address_parts.append(' '.join(street_part))
    
    # Unit part: "{street_unit}"
    if components['street_unit']:
        address_parts.append(components['street_unit'])
    
    # City part: "{city}"
    if components['city']:
        address_parts.append(components['city'])
    
    # State and zip part: "{state} {postal_code}"
    state_zip = []
    if components['state']:
        state_zip.append(components['state'])
    if components['postal_code']:
        state_zip.append(components['postal_code'])
    
    if state_zip:
        address_parts.append(' '.join(state_zip))
    
    # Join all parts with commas
    return ', '.join(address_parts)



def extract_permit_primary_number(permit_number):
    """
    Extract the primary number from a permit number, preserving leading zeros.
    """
    if not permit_number:
        return None

    try:
        # 1) MSS-style: "2012-MSS-MOV-00011"
        if '-' in permit_number and 'MSS' in permit_number:
            parts = permit_number.split('-')
            if len(parts) >= 4:
                return parts[-1]

        # 2) MV-style no hyphens: "MV20120007"
        elif permit_number.startswith('MV') and '-' not in permit_number:
            return permit_number[2:]

        # 3) MV-style with hyphens: "MV00-0002"
        elif permit_number.startswith('MV') and '-' in permit_number:
            parts = permit_number.split('-')
            if len(parts) >= 2:
                return parts[-1]

        # 4) **NEW**: any other hyphenated form, e.g. "91-1872"
        elif '-' in permit_number:
            parts = permit_number.split('-')
            return parts[-1]

        # fallback
        print(f"Warning: Couldn't extract primary number from {permit_number}")
        return None

    except Exception as e:
        print(f"Error extracting primary number from {permit_number}: {e}")
        return None


def parse_mmddyyyy(s: str):
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if s.lower() == 'null' or s == '':
        return None
    
   
    formats = [
        "%m/%d/%Y",    # Original format: 02/07/2019
        "%Y-%m-%d",    # Your scraped format: 2019-02-07
        "%m-%d-%Y",    # Alternative: 02-07-2019
        "%d/%m/%Y",    # European: 07/02/2019
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    
    # If none worked, return None
    return None