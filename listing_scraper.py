# This file is responsible for visiting accela website
# and extracting new permits from in weekly range and return.

import asyncio
import logging
from playwright.async_api import async_playwright, Page, TimeoutError


from utilities import (
    select_dropdown_by_visible_text,
    click_element,
    put_date,
    get_date_range
)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
       
    ]
)

permit_types = [
                "Building Revision",
                "Building Commercial", 
                "Building Residential", 
                "Demolition Permit",
                "Electrical Permit",
                "Mechanical Permit",
                "Moving", 
                "Plumbing Permit"
                ]

async def navigate_with_retry(page, url, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            timeout = 30000 * (attempt + 1)  # 30s, 60s, 90s
            logging.info(f"Navigation attempt {attempt + 1}/{max_attempts}, timeout: {timeout/1000}s")
            
            await page.goto(url, timeout=timeout, wait_until='domcontentloaded' if attempt > 0 else 'load')
            await page.wait_for_selector('body', timeout=5000)
            return True
            
        except TimeoutError as e:
            logging.warning(f"Navigation timeout on attempt {attempt + 1}: {str(e)}")
            if attempt < max_attempts - 1:
                await page.wait_for_timeout(5000)
            else:
                return False
        except Exception as e:
            logging.error(f"Navigation error on attempt {attempt + 1}: {str(e)}")
            return False
    return False

async def main():
    """
    Main scraper function to fetch permits from the first page
    and continue until no more pages are available
    
    """
    permit_data = []
    
    logging.info("Starting permit scraper")
   
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        # Set navigation timeout to handle slow page loads
        page.set_default_timeout(30000)  # 30 seconds
        
        try:
            # Navigate to the main page
            main_url = "https://aca-prod.accela.com/MISSOULA/Cap/CapHome.aspx?module=Building"
            
            if not await navigate_with_retry(page, main_url):
                logging.error("Failed to load main page after retries")
                return permit_data
            
            # Process each license type
            for permit in permit_types:
                logging.info(f"Processing permit type: {permit}")
                
                try:
                    # Check if we need to navigate back to home
                    if "CapHome.aspx" not in page.url:
                        if not await navigate_with_retry(page, main_url, max_attempts=2):
                            logging.error(f"Could not navigate back for permit {permit}")
                            continue
                    
                    await select_dropdown_by_visible_text(
                        page, 
                        "ctl00_PlaceHolderMain_generalSearchForm_ddlGSPermitType",
                        permit)
                    
                    # Get date range
                    previous_date_str, current_date = get_date_range()
                    logging.info(f"Date range: {previous_date_str} to {current_date}")
                    
                    # Set start date (clicking to focus on enter custom date in both fields)
                    start_end_date = [  
                                      ('ctl00_PlaceHolderMain_generalSearchForm_txtGSStartDate', previous_date_str),
                                      ('ctl00_PlaceHolderMain_generalSearchForm_txtGSEndDate', current_date)
                                  ]
                    for element_id, date_str in start_end_date:
                        await click_element(
                            page=page,
                            element_id=element_id
                        )
                        await put_date(
                            page=page,
                            date_str=date_str,
                            element_id=element_id
                        )
                    
                    # Click search button for results in given date range
                    logging.info("Clicking search button")
                    await page.wait_for_selector('//div/a[@id="ctl00_PlaceHolderMain_btnNewSearch"]', state='visible')
                    await page.click('//div/a[@id="ctl00_PlaceHolderMain_btnNewSearch"]')
                    await page.wait_for_timeout(6000)
                    
                    #it means there is only one permit and showing their detail page instead of listings page
                    currentUrl = page.url
                    if "CapDetail.aspx?" in currentUrl:

                        table = await page.query_selector('#tbl_worklocation')

                        # Then find the bolded address span within that table
                        address_element = await table.query_selector(
                            'xpath=.//td[contains(@class,"NotBreakWord")]//span[contains(@class,"fontbold")]'
                        )

                        # Extract the text (or None if it wasn't found)
                        address = (await address_element.text_content()).strip() if address_element else None
                        address = address + ', MT' if address else 'MT'

                        row_data = {
                                    "permit_number": await page.text_content('#ctl00_PlaceHolderMain_lblPermitNumber'),
                                    "permit_url": currentUrl,
                                    "address": address,
                                  }
                                                       
                        permit_data.append(row_data)
                        print("This is Row data:", row_data)
                        await navigate_with_retry(page, main_url, max_attempts=2)
                        continue
                        
                    # We always start from page 1
                    page_num = 1
                    try:
                        active_page = await page.query_selector('.SelectedPageButton')
                        if active_page:
                            active_page_text = await active_page.text_content()
                            if active_page_text.isdigit():
                                page_num = int(active_page_text)
                                logging.info(f"Verified current page: {page_num}")
                    except Exception as e:
                        logging.warning(f"Could not verify current page number: {str(e)}")
                    
                    relative_url = "https://aca-prod.accela.com"
                    max_retries = 3
                    
                    # Pagination loop continues until there are no more pages
                    while True:
                        logging.info(f"Processing page {page_num}")
                        
                        # Validate we're on a results page by checking for table header
                        header_selector = 'table.ACA_GridView.ACA_Grid_Caption > tbody > tr.ACA_TabRow_Header'
                        try:
                            await page.wait_for_selector(header_selector, timeout=10000)
                        except TimeoutError:
                            logging.warning(f"Could not find results table header on page {page_num}. May have reached the end.")
                            break
                            
                        # Wait for rows to be fully loaded
                        await page.wait_for_selector('table.ACA_GridView.ACA_Grid_Caption > tbody > tr:not(.ACA_TabRow_Header):not(.ACA_Table_Pages)', timeout=10000)
                        
                        # Get only permit rows (exclude header and pagination rows)
                        all_rows = await page.query_selector_all('table.ACA_GridView.ACA_Grid_Caption > tbody > tr:not(.ACA_TabRow_Header):not(.ACA_Table_Pages)')
                        
                        logging.info(f"Found {len(all_rows)} permit rows on page {page_num}")
                        
                        if len(all_rows) == 0:
                            logging.warning(f"No permit rows found on page {page_num}. May have reached the end.")
                            break
                        
                        for row in all_rows:
                            try:
                                # Validate this is a permit row by checking for the permit number
                                permit_number_element = await row.query_selector('xpath=.//td[3]//span')
                                
                                if not permit_number_element:
                                    logging.warning("Skipping row - no permit number element found")
                                    continue
                                
                                permit_number = await permit_number_element.text_content()
                                
                                # Additional validation - permit numbers usually have a specific format
                                if not permit_number or not permit_number.strip() or "Next" in permit_number:
                                    logging.warning(f"Skipping invalid permit number: {permit_number}")
                                    continue
                                
                                # getting permit href using XPath
                                permit_link = await row.query_selector('xpath=.//td[3]//a')
                                
                                # getting listing url from permit_link
                                permit_url = await permit_link.get_attribute('href') if permit_link else None
                                absolute_url = relative_url + permit_url if permit_url else ""
                                if "doPostBack" in absolute_url:
                                    continue
                                
                                # permit address, this address is only available on listings page, no need to 
                                # update on updates run, becz we visit detail pages onlys
                                address_element = await row.query_selector('xpath=.//td[6]//span')
                                address = await address_element.text_content() if address_element else None
                                
                                
                                row_data = {
                                    "permit_number": permit_number,
                                    "permit_url": absolute_url,
                                    "address": address,
                                  
                                }
                                
                                # Validate the data before saving
                                if not all([permit_number, absolute_url]):
                                    logging.warning(f"Skipping incomplete data: {row_data}")
                                    continue
                                
                                print(row_data, "\n")
                                permit_data.append(row_data)
                                
                            except Exception as e:
                                logging.error(f"Error processing row: {str(e)}")
                                continue
                     
                        next_button = None
                        retry_count = 0
                        
                        while retry_count < max_retries and not next_button:
                            try:
                                # More specific selector to ensure we get the Next button
                                next_button = await page.query_selector('//td[contains(@class, "aca_pagination_PrevNext")]//a[contains(text(), "Next >")]')
                                
                                if next_button:
                                    logging.info(f"Found Next button on page {page_num}, navigating to next page")
                                    
                                    # Check if the button is disabled or not clickable
                                    is_disabled = await page.evaluate('''
                                        (element) => {
                                            return element.disabled || 
                                                   element.classList.contains('disabled') || 
                                                   element.parentElement.classList.contains('disabled') ||
                                                   window.getComputedStyle(element).cursor === 'not-allowed';
                                        }
                                    ''', next_button)
                                    
                                    if is_disabled:
                                        logging.info("Next button is disabled. Reached the end of pagination.")
                                        break
                                    
                                    # Click the next button
                                    await page.evaluate('(element) => element.click()', next_button)
                                    
                                    # Wait for navigation to complete by checking for loading indicators
                                    try:
                                        # Wait for loading to start
                                        await page.wait_for_selector('.ACA_Wait', state='visible', timeout=3000)
                                        # Wait for loading to finish
                                        await page.wait_for_selector('.ACA_Wait', state='hidden', timeout=20000)
                                    except:
                                        # If we don't see loading indicators, just wait a fixed time
                                        await page.wait_for_timeout(10000)
                                    
                                    # Verify we moved to the next page
                                    new_page_verified = False
                                    try:
                                        active_page = await page.query_selector('.SelectedPageButton')
                                        if active_page:
                                            active_page_text = await active_page.text_content()
                                            if active_page_text.isdigit():
                                                new_page = int(active_page_text)
                                                if new_page > page_num:
                                                    logging.info(f"Successfully moved to page {new_page}")
                                                    page_num = new_page
                                                    new_page_verified = True
                                                else:
                                                    logging.warning(f"Navigation may have failed. Still on page {active_page_text}")
                                    except Exception as e:
                                        logging.warning(f"Could not verify new page number: {str(e)}")
                                    
                                    # If we couldn't verify from the pagination, just increment
                                    if not new_page_verified:
                                        page_num += 1
                                else:
                                    logging.info(f"No Next button found on page {page_num}. Reached the end.")
                                    break
                                    
                            except Exception as e:
                                retry_count += 1
                                logging.warning(f"Error clicking Next button (attempt {retry_count}/{max_retries}): {str(e)}")
                                await page.wait_for_timeout(5000)  # Wait before retry
                        
                        if not next_button:
                            logging.info("No more pages to process")
                            break
                
                except Exception as e:
                    logging.error(f"Error processing permit type {permit}: {str(e)}")
                    continue
                
        except Exception as e:
            logging.error(f"Fatal error in main: {str(e)}")
        
        finally:
            await browser.close()
            logging.info(f"Scraping completed. Total permits collected: {len(permit_data)}")
    
    return permit_data

if __name__ == "__main__":
    permits = asyncio.run(main())