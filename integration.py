# integration.py
# This file integrates listing_scraper (extracts weekly permits from listing pages)
# and detail_scraper (visits detail pages to extract latest data)
# Now includes checkpoint/resume functionality for maintenance mode handling

import sys
import os
import json
import asyncio
import logging
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.async_api import async_playwright
from listing_scraper import main as scrape_listings
from detail_scraper import scrape_permit_details

from db_exporters_upsert import (
    DatabaseConnection,
    PropertyAddressExporter,
    PermitExporter,
    ContactExporter,
    PropertyDetailExporter,
    PermitInspectionExporter,
    PermitValuationExporter,
    PermitProcessExporter,
    PermitRelatedExporter,
    PermitConditionExporter,
)

from models.permit_model import Permit
from models.property_address_model import PropertyAddress

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


async def run():
    checkpoint_file = 'integration_checkpoint.json'
    worklist_file = 'worklist_snapshot.json'
    
    # Step 1: Scrape listing pages to get new permits
    new_rows = await scrape_listings()
    new_nums = {r["permit_number"] for r in new_rows}
    logger.info("Found %d new permits from website", len(new_rows))

    # Step 2: Prepare DB and session for lookups
    db = DatabaseConnection()
    db.create_tables()
    Session = db.Session
    lookup_sess = Session()

    # Get completed permits (never re-scrape these)
    completed_nums = {
        num for (num,) in
        lookup_sess
            .query(Permit.full_permit_number)
            .filter_by(is_completed=True)
            .all()
    }
    logger.info("Found %d completed permits in DB (will skip)", len(completed_nums))
    
    # Step 3: Check if we're resuming from a previous crash/maintenance
    resuming = False
    saved_worklist = []
    processed_permits = set()
    
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)
            resuming = True
            processed_permits = set(checkpoint.get('processed', []))
            logger.info("="*60)
            logger.info("RESUMING FROM CHECKPOINT")
            logger.info(f"Already processed: {len(processed_permits)} permits")
            logger.info(f"Last permit: {checkpoint.get('last_permit', 'N/A')}")
            logger.info(f"Checkpoint time: {checkpoint.get('timestamp', 'N/A')}")
            logger.info("="*60)
    
    # Step 4: Build or load worklist
    if resuming and os.path.exists(worklist_file):
        # Use saved worklist for consistency
        with open(worklist_file, 'r') as f:
            saved_worklist = json.load(f)
            logger.info(f"Loaded saved worklist with {len(saved_worklist)} items")
        worklist = saved_worklist
    else:
        # Build fresh worklist
        # Find incomplete permits not in this week's scrape
        to_update = (
            lookup_sess.query(Permit)
                .filter_by(is_completed=False)
                .filter(~Permit.full_permit_number.in_(new_nums))
                .filter(~Permit.full_permit_number.in_(completed_nums))
                .all()
        )
        logger.info("%d existing incomplete permits to re-scrape", len(to_update))

        # Build worklist: new first, then old incomplete
        worklist = [
            row for row in new_rows
            if row["permit_number"] not in completed_nums
        ]

        for p in to_update:
            worklist.append({
                "permit_number": p.full_permit_number,
                "permit_url": p.permit_url,
                "address": None,
            })
        
        # Save worklist snapshot for potential resume
        with open(worklist_file, 'w') as f:
            json.dump(worklist, f, indent=2)
        logger.info(f"Saved worklist snapshot: {len(worklist)} total permits to process")

    # Step 5: Initialize all exporters
    prop_ex = PropertyAddressExporter(db)
    permit_ex = PermitExporter(db)
    contact_ex = ContactExporter(db)
    detail_ex = PropertyDetailExporter(db)
    insp_ex = PermitInspectionExporter(db)
    val_ex = PermitValuationExporter(db)
    proc_ex = PermitProcessExporter(db)
    rel_ex = PermitRelatedExporter(db)
    cond_ex = PermitConditionExporter(db)

    maintenance_mode = False
    
    try:
        # Step 6: Drive Playwright through the worklist
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless = True)
            ctx = await browser.new_context()
            page = await ctx.new_page()
            page.set_default_timeout(30000)

            for idx, row in enumerate(worklist):
                num = row["permit_number"]
                url = row["permit_url"]
                addr = row["address"]

                # Skip if already processed in this or previous run
                if num in processed_permits:
                    logger.info(f"[{idx+1}/{len(worklist)}] Skipping {num} - already processed")
                    continue

                logger.info(f"[{idx+1}/{len(worklist)}] -> scraping details for {num}")

                try:
                    # Fetch all detail-tab data
                    (
                        basic_details, app_parcel, contacts,
                        conditions, inspections,
                        valuations, related_recs,
                        processes
                    ) = await scrape_permit_details(page, url)
                    
                except Exception as e:
                    # Check for maintenance mode
                    if str(e) == "MAINTENANCE_MODE":
                        logger.error("="*60)
                        logger.error("MAINTENANCE MODE DETECTED")
                        logger.error("Site is under maintenance. Saving checkpoint and exiting...")
                        logger.error("="*60)
                        maintenance_mode = True
                        break
                    
                    logger.error(f"Error scraping {num} at {url}: {e}")
                    continue

                # Merge CSV/listing data with scraped details
                basic_details.update({
                    "permit_number": num,
                    "permit_url": url,
                    "address": addr,
                })

                # Upsert property address
                if addr:
                    pa = prop_ex.upsert(basic_details, app_parcel)
                else:
                    # For updates, get existing property address
                    existing = (
                        lookup_sess
                        .query(Permit)
                        .filter_by(full_permit_number=num)
                        .one()
                    )
                    pa = (
                        lookup_sess
                        .query(PropertyAddress)
                        .filter_by(property_address_pk=existing.property_address_pk)
                        .one()
                    )

                # Upsert the permit itself
                permit_obj = permit_ex.upsert(
                    basic_details,
                    app_parcel,
                    processes,
                    pa.property_address_pk,
                    # owner/license FKs will be patched below
                )
                pk = permit_obj.permit_pk

                # Owner section lives in basic_details under owner_*
                if any(k.startswith("owner_") for k in basic_details):
                    owner = contact_ex.upsert(basic_details, pk, "owner")
                    permit_obj.property_owner_pk = owner.contact_pk
                            
                # Licensed professional also lives in basic_details under license_pro_*
                if any(k.startswith("license_pro_") for k in basic_details):
                    lic = contact_ex.upsert(basic_details, pk, "license_pro")
                    permit_obj.contractor_company_pk = lic.contact_pk
                
                # Additional contacts
                for block in contacts:
                    prefix = block["which_source_prefix"]
                    if prefix not in ("owner", "license_pro"):
                        contact_ex.upsert(block, pk, prefix)

                # Commit those back-patched FKs
                permit_ex.session.commit()

                # Property detail
                detail_ex.upsert(pk, pa.property_address_pk, permit_obj.property_owner_pk, app_parcel)

                # Inspections
                insp_ex.upsert(inspections, pk)

                # Valuations
                val_ex.upsert(pk, valuations)

                # Processes
                proc_ex.upsert(pk, processes)

                # Related permits
                rel_ex.upsert(pk, num, related_recs)

                # Conditions
                cond_ex.upsert(pk, conditions)

                # Mark as successfully processed
                processed_permits.add(num)
                
                # Update checkpoint after each successful permit
                with open(checkpoint_file, 'w') as f:
                    json.dump({
                        'processed': list(processed_permits),
                        'last_permit': num,
                        'timestamp': datetime.now().isoformat(),
                        'total_in_worklist': len(worklist)
                    }, f, indent=2)
                
                logger.info(f"Successfully processed {num} ({len(processed_permits)}/{len(worklist)})")

            await browser.close()

        # Reconcile any late-bound related_permit_pk
        logger.info("Reconciling related permit PKs...")
        rel_ex.reconcile_related_pks()

        # If completed successfully, clean up checkpoint files
        if not maintenance_mode:
            if os.path.exists(checkpoint_file):
                os.remove(checkpoint_file)
                logger.info("Removed checkpoint file")
            if os.path.exists(worklist_file):
                os.remove(worklist_file)
                logger.info("Removed worklist snapshot")
            logger.info("="*60)
            logger.info("SCRAPING COMPLETED SUCCESSFULLY")
            logger.info(f"Total permits processed: {len(processed_permits)}")
            logger.info("="*60)

    finally:
        # Tear down everything
        prop_ex.close()
        permit_ex.close()
        contact_ex.close()
        detail_ex.close()
        insp_ex.close()
        val_ex.close()
        proc_ex.close()
        rel_ex.close()
        cond_ex.close()
        lookup_sess.close()
        
        if maintenance_mode:
            logger.warning("="*60)
            logger.warning("EXITING DUE TO MAINTENANCE MODE")
            logger.warning(f"Processed {len(processed_permits)} permits before interruption")
            logger.warning("Run the script again to resume from checkpoint")
            logger.warning("="*60)
            sys.exit(1)
        
        logger.info("All done.")


if __name__ == "__main__":
    asyncio.run(run())