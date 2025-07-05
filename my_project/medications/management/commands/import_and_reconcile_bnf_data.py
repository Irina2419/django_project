# medications/management/commands/import_and_reconcile_bnf_data.py

import requests
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from datetime import datetime
import os
from django.conf import settings
from django.db.models import Q

from medications.models import BNFHierarchy, ChemicalComposition, MedicationProduct

# --- NHSBSA API Configuration ---
NHSBSA_API_URL = "https://opendata.nhsbsa.net/api/action/datastore_search"
BNF_RESOURCE_ID = "BNF_CODE_CURRENT_202505_VERSION_88" # The specific resource ID for BNF data

# API_TOKEN is usually not required for public datastore_search endpoints
API_TOKEN = os.environ.get("NHSBSA_API_TOKEN", "")

class Command(BaseCommand):
    help = 'Imports full BNF hierarchy and chemical composition data from NHSBSA API, then reconciles MedicationProducts.'

    def fetch_all_records(self, resource_id): # Removed query_string parameter
        """Fetches all records from a given NHSBSA datastore resource using pagination."""
        all_records = []
        offset = 0
        limit = 1000 # Max limit per request, common for CKAN APIs

        self.stdout.write(self.style.NOTICE(f"Fetching data for resource_id: {resource_id}"))

        while True:
            params = { # Use params for GET request
                "resource_id": resource_id,
                "limit": limit,
                "offset": offset
            }
            # No 'q' parameter here for full bulk fetch

            headers = {'content-type': 'application/json'}
            if API_TOKEN:
                headers['authorization'] = API_TOKEN

            try:
                resp = requests.get(NHSBSA_API_URL, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

                if not data['success']:
                    raise CommandError(f"API request failed: {data.get('error', {}).get('message', 'Unknown error')}")

                records = data['result']['records']
                all_records.extend(records)

                if len(records) < limit: # No more records
                    break
                offset += limit
                self.stdout.write(self.style.NOTICE(f"Fetched {len(all_records)} records so far..."))

            except requests.exceptions.RequestException as e:
                raise CommandError(f"API request failed: {e}")
            except KeyError:
                raise CommandError(f"Unexpected API response structure: {data}")

        self.stdout.write(self.style.SUCCESS(f"Finished fetching {len(all_records)} total records."))
        return all_records

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting full BNF data import and reconciliation via API."))

        # --- Step 1: Fetch BNF Data from API (Full Bulk Fetch) ---
        try:
            bnf_records = self.fetch_all_records(BNF_RESOURCE_ID) # Call without query_string
            if not bnf_records:
                raise CommandError("No BNF records fetched from API. Check RESOURCE_ID and API status.")

            df = pd.DataFrame(bnf_records)
            self.stdout.write(self.style.SUCCESS(f"Successfully loaded BNF data into DataFrame with {len(df)} rows."))

            # --- RENAME COLUMNS TO MATCH YOUR DJANGO MODEL FIELDS ---
            # These are the EXACT keys from your API response!
            df.rename(columns={
                'BNF_PRESENTATION_CODE': 'bnf_code_15digit', # This is the 15-digit code
                'BNF_CHAPTER_CODE': 'bnf_chapter_code',
                'BNF_CHAPTER': 'bnf_chapter_name',
                'BNF_SECTION_CODE': 'bnf_section_code',
                'BNF_SECTION': 'bnf_section_name',
                'BNF_PARAGRAPH_CODE': 'bnf_paragraph_code',
                'BNF_PARAGRAPH': 'bnf_paragraph_name',
                'BNF_CHEMICAL_SUBSTANCE': 'bnf_chemical_substance',
                'BNF_PRESENTATION': 'bnf_presentation_description',
                'YEAR_MONTH': 'bnf_version', # Using YEAR_MONTH as BNF Version
                # Valid From/To Dates are not directly in this API response, will derive or set defaults
            }, inplace=True)

            # Add Valid From Date (assuming first of the month from YEAR_MONTH)
            df['valid_from_date'] = pd.to_datetime(df['bnf_version'] + '-01', errors='coerce').dt.date
            df['valid_to_date'] = None # No 'Valid To Date' in this API resource

            # Drop rows where essential data is missing
            df.dropna(subset=['bnf_code_15digit', 'bnf_chemical_substance', 'bnf_presentation_description', 'valid_from_date'], inplace=True)

            imported_chemicals = 0
            imported_bnf_entries = 0
            reconciled_products = 0

            # --- Step 2: Import BNF Hierarchy and Chemical Composition ---
            self.stdout.write(self.style.NOTICE("Importing BNF Hierarchy and Chemical Compositions..."))
            with transaction.atomic():
                for index, row in df.iterrows():
                    bnf_code_15digit = str(row['bnf_code_15digit']).strip()
                    bnf_chemical_substance = str(row['bnf_chemical_substance']).strip()

                    # Create/Get Chemical Composition
                    chemical_obj, created_chem = ChemicalComposition.objects.get_or_create(
                        chemical_name=bnf_chemical_substance,
                        defaults={'chemical_description': f"From BNF API: {bnf_chemical_substance}"}
                    )
                    if created_chem:
                        imported_chemicals += 1

                    # Create/Get BNF Hierarchy
                    bnf_entry, created_bnf = BNFHierarchy.objects.update_or_create(
                        bnf_code_15digit=bnf_code_15digit,
                        defaults={
                            'bnf_chapter_code': row.get('bnf_chapter_code'),
                            'bnf_chapter_name': row.get('bnf_chapter_name'),
                            'bnf_section_code': row.get('bnf_section_code'),
                            'bnf_section_name': row.get('bnf_section_name'),
                            'bnf_paragraph_code': row.get('bnf_paragraph_code'),
                            'bnf_paragraph_name': row.get('bnf_paragraph_name'),
                            'bnf_chemical_substance': bnf_chemical_substance,
                            'bnf_presentation_description': row.get('bnf_presentation_description'),
                            'bnf_version': row.get('bnf_version'),
                            'valid_from_date': row.get('valid_from_date'),
                            'valid_to_date': row.get('valid_to_date'),
                        }
                    )
                    if created_bnf:
                        imported_bnf_entries += 1

            self.stdout.write(self.style.SUCCESS(
                f"BNF Import complete! Imported {imported_chemicals} new chemicals and {imported_bnf_entries} BNF hierarchy entries."
            ))

            # --- Step 3: Reconcile existing MedicationProducts from eMIT with BNF data ---
            self.stdout.write(self.style.NOTICE("Attempting to reconcile existing eMIT products with BNF data..."))
            emit_products = MedicationProduct.objects.filter(
                npc_code__isnull=False,
                bnf_code_15digit__bnf_code_15digit__startswith='BNF_NPC_' # Filter for placeholder BNF links
            )

            reconciled_products_count = 0 # Reset counter for reconciliation

            for product in emit_products:
                # Try to find a matching BNF entry using the product_name from eMIT
                # This is the reconciliation logic.
                # We'll use case-insensitive exact match for now.
                matching_bnf = BNFHierarchy.objects.filter(
                    bnf_presentation_description__iexact=product.product_name
                ).first()

                if matching_bnf:
                    # Update the MedicationProduct with the real BNF and Chemical links
                    product.bnf_code_15digit = matching_bnf
                    product.chemical_name = ChemicalComposition.objects.get(chemical_name=matching_bnf.bnf_chemical_substance)
                    product.save()
                    reconciled_products_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Reconciled NPC {product.npc_code} ('{product.product_name}') with BNF {matching_bnf.bnf_code_15digit}"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"Could not reconcile NPC {product.npc_code} ('{product.product_name}') with any BNF entry by exact name match."
                    ))

            self.stdout.write(self.style.SUCCESS(
                f"Reconciliation complete! Reconciled {reconciled_products_count} eMIT products with BNF data."
            ))

        except requests.exceptions.RequestException as e:
            raise CommandError(f"API request failed: {e}")
        except Exception as e:
            raise CommandError(f"Error during BNF import and reconciliation: {e}")