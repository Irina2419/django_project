# medications/admin.py

from django.contrib import admin
from .models import (
    ChemicalComposition,
    BNFHierarchy,
    MedicationProduct,
    MedicationPricingHistory,
    CostEffectivenessAppraisal
)

# Register your models here so they appear in the Django admin interface
admin.site.register(ChemicalComposition)
admin.site.register(BNFHierarchy)
admin.site.register(MedicationProduct)
admin.site.register(MedicationPricingHistory)
admin.site.register(CostEffectivenessAppraisal)