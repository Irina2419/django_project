# medications/management/commands/import_emit_data.py

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from datetime import datetime
import os
from django.conf import settings

from medications.models import MedicationProduct, MedicationPricingHistory, BNFHierarchy, ChemicalComposition

DATA_FILE_PATH = os.path.join(
    settings.DATA_DIR,
    'emit_national_database.ods'
)

class Command(BaseCommand):
    help = 'Imports medication pricing data from the eMIT ODS file into the database.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Starting import from {DATA_FILE_PATH}"))

        if not os.path.exists(DATA_FILE_PATH):
            raise CommandError(f"eMIT ODS file not found at: {DATA_FILE_PATH}")

        try:
            # --- MODIFIED pd.read_excel to specify header row ---
            # Try header=1 (meaning the 2nd row of the spreadsheet is the header)
            df = pd.read_excel(DATA_FILE_PATH, engine='odf', header=1)
            self.stdout.write(self.style.SUCCESS(f"Successfully loaded ODS file with {len(df)} rows."))

            # --- TEMPORARY DIAGNOSTIC LINE (KEEP THIS FOR NOW) ---
            self.stdout.write(self.style.WARNING(f"Columns found in ODS: {df.columns.tolist()}"))
            # --- END TEMPORARY DIAGNOSTIC LINE ---

            # ... rest of the script (the df.rename section and subsequent logic) remains the same as my LAST full code block ...
            # It should still have the full df.rename with all 5 columns:
            df.rename(columns={
                'NPC Code': 'npc_code',
                'Name & PackSize': 'product_name_emit',
                'Weighted Average Price': 'average_price_paid_gbp',
                'Quantity': 'estimated_annual_usage',
                'Standard Deviation Of Price': 'price_change_measure'
            }, inplace=True)

            df['average_price_paid_gbp'] = pd.to_numeric(df['average_price_paid_gbp'], errors='coerce')
            df['estimated_annual_usage'] = pd.to_numeric(df['estimated_annual_usage'], errors='coerce')
            df['price_change_measure'] = pd.to_numeric(df['price_change_measure'], errors='coerce')

            df.dropna(subset=['npc_code', 'average_price_paid_gbp'], inplace=True)

            period_start_date = datetime(2023, 7, 1).date()
            period_end_date = datetime(2024, 6, 30).date()

            imported_products = 0
            imported_prices = 0

            with transaction.atomic():
                for index, row in df.iterrows():
                    npc_code = str(row['npc_code']).strip()
                    emit_product_name = str(row['product_name_emit']).strip()
                    price_value = row['average_price_paid_gbp']
                    usage_estimate = row.get('estimated_annual_usage')
                    price_change_measure = row.get('price_change_measure')

                    if pd.isna(price_value):
                        self.stdout.write(self.style.WARNING(f"Skipping row {index}: Price is missing or invalid for NPC Code {npc_code}"))
                        continue

                    chemical_obj, _ = ChemicalComposition.objects.get_or_create(
                        chemical_name=f"CHEM_NPC_{npc_code}",
                        defaults={'chemical_description': f"Placeholder for NPC Code {npc_code}"}
                    )

                    placeholder_bnf_code = f"BNF_NPC_{npc_code}"
                    bnf_obj, bnf_created = BNFHierarchy.objects.get_or_create(
                        bnf_code_15digit=placeholder_bnf_code,
                        defaults={
                            'bnf_chapter_code': 'XX',
                            'bnf_chapter_name': 'Placeholder Chapter',
                            'bnf_section_code': 'XXXXX',
                            'bnf_section_name': 'Placeholder Section',
                            'bnf_paragraph_code': 'XXXXXXX',
                            'bnf_paragraph_name': 'Placeholder Paragraph',
                            'bnf_chemical_substance': chemical_obj.chemical_name,
                            'bnf_presentation_description': emit_product_name,
                            'bnf_version': 'eMIT Placeholder',
                            'valid_from_date': period_start_date,
                            'valid_to_date': None,
                        }
                    )
                    if bnf_created:
                        self.stdout.write(self.style.NOTICE(f"Created placeholder BNF entry for {placeholder_bnf_code}"))

                    med_product, created = MedicationProduct.objects.get_or_create(
                        npc_code=npc_code,
                        defaults={
                            'product_name': emit_product_name,
                            'bnf_code_15digit': bnf_obj,
                            'chemical_name': chemical_obj,
                            'latest_average_price_gbp': price_value,
                            'cost_effectiveness_status': 'Unknown'
                        }
                    )
                    if created:
                        imported_products += 1
                        self.stdout.write(self.style.SUCCESS(f"Created new product (NPC: {npc_code})"))
                    else:
                        med_product.latest_average_price_gbp = price_value
                        med_product.product_name = emit_product_name
                        med_product.save()
                        self.stdout.write(self.style.WARNING(f"Updated existing product (NPC: {npc_code})"))

                    MedicationPricingHistory.objects.create(
                        product=med_product,
                        source='eMIT Hospital Data',
                        price_gbp=price_value,
                        period_start=period_start_date,
                        period_end=period_end_date,
                        usage_estimate=usage_estimate,
                        price_change_measure=price_change_measure
                    )
                    imported_prices += 1

            self.stdout.write(self.style.SUCCESS(
                f"Import complete! Imported {imported_products} new products and {imported_prices} pricing records."
            ))

        except FileNotFoundError:
            raise CommandError(f"eMIT ODS file not found at: {DATA_FILE_PATH}")
        except Exception as e:
            raise CommandError(f"Error during import: {e}")