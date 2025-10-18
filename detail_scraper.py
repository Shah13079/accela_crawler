# details_scraper.py
import asyncio
import logging
import traceback
from playwright.async_api import Page
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright._impl._errors import Error as PlaywrightError

from utilities import (
    license_pro_info,
    extract_owner_info,
    ext_application_info,
    extract_parcel_info,
    extract_table_list_info,
    extract_contact_info_blocks,
    parse_conditions,
    parse_inspections,
    parse_valuation_table,
    parse_related_records_table,
    parse_process_info,
)

logger = logging.getLogger(__name__)

async def safe_get_text(page: Page, selector: str, timeout: int = 10000, default=None):
    """Safely extract text content from a selector, or return default."""
    try:
        locator = page.locator(selector).first
        if await locator.count() > 0:
            return await locator.text_content(timeout=timeout)
    except Exception as e:
        logger.warning(f"[safe_get_text] selector={selector} → {e}")
    return default

async def safe_get_html(page: Page, selector: str, timeout: int = 10000, default=None):
    """Safely extract inner HTML from a selector, or return default."""
    try:
        locator = page.locator(selector)
        if await locator.count() > 0:
            return await locator.inner_html(timeout=timeout)
    except Exception as e:
        logger.warning(f"[safe_get_html] selector={selector} → {e}")
    return default

async def safe_element_exists(page: Page, selector: str) -> bool:
    """Return True if selector exists on the page."""
    try:
        locator = page.locator(selector)
        return await locator.count() > 0
    except Exception as e:
        logger.warning(f"[safe_element_exists] selector={selector} → {e}")
        return False


async def scrape_permit_details(page: Page, url: str):
    """
    Navigate to the permit detail page at `url`, scrape all tabs, and return
    a tuple of eight lists/dicts:
      (basic_details,
       app_parcel_info_row,
       related_contacts,
       all_conditions,
       all_inspection,
       valuation_info,
       related_records_info,
       process_info)
    """
    basic_details = {}
    app_parcel_info_row = {}
    related_contacts = []
    all_conditions = []
    valuation_info = []
    related_records_info = []
    process_info = []
    all_inspections = []
    # Try multiple loading strategies
    loading_strategies = [
  
        {"wait_until": "domcontentloaded", "timeout": 30000},
        {"wait_until": "load", "timeout": 60000},
    ]
    
    page_loaded = False
    
    for i, strategy in enumerate(loading_strategies):
        try:
            await page.goto(url, **strategy)

            # Check for maintenance message immediately after page loads
            maintenance_text = "Accela Citizen Access Portal is unavailable at this time due to maintenance"
            page_content = await page.content()
            if maintenance_text in page_content:
                logger.error(f"[MAINTENANCE DETECTED] Site is under maintenance. Stopping scraper.")
                raise Exception("MAINTENANCE_MODE")

            # Wait for key element to ensure page is actually loaded
            await page.wait_for_selector('//span[@id="ctl00_PlaceHolderMain_lblPermitType"]', timeout=10000)
            page_loaded = True
            break
        except Exception as e:
            if str(e) == "MAINTENANCE_MODE":
                raise
            if i < len(loading_strategies) - 1:
                await asyncio.sleep(2)  
    
    if not page_loaded:
        logger.error(f"[scrape_permit_details] All loading strategies failed for {url}")
        return (basic_details, app_parcel_info_row, related_contacts,
                all_conditions, all_inspections, valuation_info,
                related_records_info, process_info)
    # Add a small wait to ensure dynamic content loads
    await page.wait_for_timeout(3000)

    try:
        basic_details["description"] = await safe_get_text(
            page,
            '//h1[contains(.,"Description:")]/following-sibling::span//table//td[2]',
            timeout=20000,
            default=None
        )
        basic_details["category"] = await safe_get_text(
            page,
            '//span[@id="ctl00_PlaceHolderMain_lblPermitType"]',
            timeout=10000,
            default=None
        )
        basic_details["permit_type"] = basic_details.get("category")

        basic_details["status"] = await safe_get_text(
            page,
            '//h1[contains(.,"Record Status:")]/span[2]',
            timeout=5000,
            default=None
        )

        basic_details["work_location"] = await safe_get_text(
            page,
            '//table[@id="tbl_worklocation"]//span[@class="fontbold"]',
            timeout=10000,
            default=None
        )

        # --- Licensed Professional ---
        if await safe_element_exists(page, '//h1/span[contains(text(),"Licensed Professional:")]/parent::node()/following-sibling::span/table/tbody/tr[1]'):
            licensed_professional_html = await safe_get_html(
                page, 
                '//h1/span[contains(text(),"Licensed Professional:")]/parent::node()/following-sibling::span/table/tbody/tr[1]'
            )
            if licensed_professional_html:
                license_p_info = license_pro_info(licensed_professional_html)
                basic_details.update(license_p_info)
            
        # Extract owner information
        if await safe_element_exists(page, '//h1/span[contains(text(),"Owner:")]/parent::node()/following-sibling::span/table/tbody/tr[1]'):
            owner_html = await safe_get_html(
                page, 
                '//h1/span[contains(text(),"Owner:")]/parent::node()/following-sibling::span/table/tbody/tr[1]'
            )
            if owner_html:
                owner_info = extract_owner_info(owner_html)
                basic_details.update(owner_info)


        # --- ASI tables / parcel ---
        app_info = {}
        if await safe_element_exists(page, '//tr[@id="trASIList"]'):
            html = await safe_get_html(page, '//tr[@id="trASIList"]')
            app_info = ext_application_info(html)

        second_table = {}
        if await safe_element_exists(page, 
                '//span[@id="ctl00_PlaceHolderMain_PermitDetailList1_tbASITList"]'):
            html = await safe_get_html(page,
                '//span[@id="ctl00_PlaceHolderMain_PermitDetailList1_tbASITList"]')
            second_table = extract_table_list_info(html)

        parcel_tab = {}
        if await safe_element_exists(page, 
                '//span[@id="ctl00_PlaceHolderMain_PermitDetailList1_tbParcelList"]'):
            html = await safe_get_html(page,
                '//span[@id="ctl00_PlaceHolderMain_PermitDetailList1_tbParcelList"]')
            parcel_tab = extract_parcel_info(html)

        app_parcel_info_row = {**app_info, **second_table, **parcel_tab}

        # --- Related contacts ---
        if await safe_element_exists(page, '//tr[@id="TRMoreDetail"]'):
            html = await safe_get_html(page, '//tr[@id="TRMoreDetail"]')
            related_contacts = extract_contact_info_blocks(html)

        # --- Valuations ---
        if await safe_element_exists(page, '//div[@id="tab-valuation_calculator"]'):
            html = await safe_get_html(page, '//div[@id="tab-valuation_calculator"]')
            valuation_info = parse_valuation_table(html)

        # --- Related records ---
        if await safe_element_exists(page, '//div[@id="tab-related_records"]'):
            html = await safe_get_html(page, '//div[@id="tab-related_records"]')
            related_records_info = parse_related_records_table(html)

        # --- Process info ---
        if await safe_element_exists(page, '//div[@id="tab-processing_status"]'):
            html = await safe_get_html(page, '//div[@id="tab-processing_status"]')
            process_info = parse_process_info(html)

        nxt = None
        # --- Conditions (may be paginated) ---
        while True:
            if await safe_element_exists(page, '//div[@id="divGeneralConditions"]'):
                html = await safe_get_html(page, '//div[@id="divGeneralConditions"]')
                all_conditions.extend(parse_conditions(html))
          
                nxt = await page.query_selector(
                    "//table[@id='ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList']"
                    "//td[contains(@class,'aca_pagination_PrevNext')]//a[text()='Next >']"
                )
            
            if not nxt:
                break
            await page.evaluate("(el)=>el.click()", nxt)
            await page.wait_for_timeout(2000)
            

        try:
            # --- Inspections ---
            await page.click("//a[contains(@class,'par-menu') and normalize-space(text())='Record Info']")
            await page.wait_for_timeout(500)
            await page.click("//ul[contains(@class,'dropdown-menu')]//a[@data-control='tab-inspections']")
            await page.wait_for_selector("//div[@id='tab-inspections' and contains(@class,'show')]", timeout=30000)
            await page.wait_for_timeout(500)
        except PlaywrightError as e:
            pass
            
        
        # 2) Detect spinner and, if it appears, reload & re-select
        try:
            # wait briefly for loading to start
            await page.wait_for_selector('#inspectionLoding:not(.ACA_Hide)', timeout=5000)
            # spinner detected → reload the page
            await page.reload()
            # re-open Record Info → Inspections
            await page.click("//a[contains(@class,'par-menu') and normalize-space(text())='Record Info']")
            await page.wait_for_timeout(500)
            await page.click("//ul[contains(@class,'dropdown-menu')]//a[@data-control='tab-inspections']")
            await page.wait_for_selector("//div[@id='tab-inspections' and contains(@class,'show')]", timeout=30000)
            # now wait for spinner to finish
            await page.wait_for_selector('#inspectionLoding', state='hidden', timeout=30000)
        except PlaywrightTimeoutError:
            # spinner never showed → proceed immediately
            pass
        nxt = None
        # 3) Paginate & scrape as usual
        while True:
            if await safe_element_exists(page, '//div[@id="inspectionTable"]'):
                html = await safe_get_html(page, '//div[@id="inspectionTable"]')
                for ins in parse_inspections(html):
                    all_inspections.append(ins)

            nxt = await page.query_selector(
                "//table[@id='ctl00_PlaceHolderMain_InspectionList_gvListCompleted']//a[normalize-space(text())='Next >']"
            )
            if not nxt:
                break

            await page.evaluate('el => el.click()', nxt)
            await page.wait_for_timeout(5000)
            await page.wait_for_selector(
                "//table[@id='ctl00_PlaceHolderMain_InspectionList_gvListCompleted']//tr[contains(@class,'InspectionListRow')]",
                timeout=30000
            )

    except Exception as e:
                logger.error(f"[scrape_permit_details] error on {url}: {e}")
                logger.error(traceback.format_exc())

    return (
        basic_details,
        app_parcel_info_row,
        related_contacts,
        all_conditions,
        all_inspections,
        valuation_info,
        related_records_info,
        process_info
    )

async def parse_detail(page: Page, url: str):
    """
    Thin wrapper if you prefer to import a single name.
    """
    return await scrape_permit_details(page, url)
