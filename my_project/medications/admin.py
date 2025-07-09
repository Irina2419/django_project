# medications/admin.py

from django.contrib import admin
from .models import (
    ChemicalComposition,
    BNFHierarchy,
    MedicationProduct,
    MedicationPricingHistory,
    # CostEffectivenessAppraisal # <--- REMOVE THIS LINE
)

admin.site.register(ChemicalComposition)
admin.site.register(BNFHierarchy)
admin.site.register(MedicationProduct)
admin.site.register(MedicationPricingHistory)
# admin.site.register(CostEffectivenessAppraisal) # <--- REMOVE THIS LINE