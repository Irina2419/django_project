# medications/views.py

from django.shortcuts import render
from .models import MedicationProduct, MedicationPricingHistory, BNFHierarchy

def medication_list(request):
    # Fetch all MedicationProducts
    # Use select_related to fetch related BNFHierarchy and ChemicalComposition in one query
    medications = MedicationProduct.objects.select_related(
        'bnf_code_15digit', # Related BNFHierarchy object
        'chemical_name'     # Related ChemicalComposition object
    ).all()

    # Prepare data for the template
    medication_data = []
    for med in medications:
        # Get latest price from pricing history (assuming ordering by -period_start)
        latest_price_obj = med.pricing_history.filter(source='eMIT Hospital Data').first()
        latest_price = latest_price_obj.price_gbp if latest_price_obj else 'N/A'

        # Get BNF Full Classification (using the @property from BNFHierarchy model)
        bnf_full_classification = med.bnf_code_15digit.full_classification if med.bnf_code_15digit else 'N/A'

        medication_data.append({
            'product_id': med.id,
            'product_name': med.product_name,
            'npc_code': med.npc_code,
            'bnf_code_15digit': med.bnf_code_15digit.bnf_code_15digit if med.bnf_code_15digit else 'N/A',
            'bnf_chapter_name': med.bnf_code_15digit.bnf_chapter_name if med.bnf_code_15digit else 'N/A',
            'bnf_chemical_substance': med.chemical_name.chemical_name if med.chemical_name else 'N/A',
            'bnf_full_classification': bnf_full_classification, # Derived property
            'latest_average_price_gbp': latest_price,
            'annual_usage_estimate_items': med.annual_usage_estimate_items, # Derived property
            'price_source': 'eMIT Hospital Data' if latest_price_obj else 'N/A',
        })

    context = {
        'medications': medication_data
    }
    return render(request, 'medications/medication_list.html', context)