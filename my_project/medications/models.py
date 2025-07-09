# medications/models.py

from django.db import models
from django.db.models import Q # Keep this import if you used it in reconciliation

# --- 1. Chemical_Composition Table ---
class ChemicalComposition(models.Model):
    chemical_name = models.CharField(max_length=255, unique=True)
    chemical_description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Chemical Composition"
        verbose_name_plural = "Chemical Compositions"

    def __str__(self):
        return self.chemical_name

# --- 2. BNF_Hierarchy Table ---
class BNFHierarchy(models.Model):
    bnf_code_15digit = models.CharField(max_length=15, primary_key=True)
    bnf_chapter_code = models.CharField(max_length=2, blank=True, null=True)
    bnf_chapter_name = models.CharField(max_length=255, blank=True, null=True)
    bnf_section_code = models.CharField(max_length=5, blank=True, null=True)
    bnf_section_name = models.CharField(max_length=255, blank=True, null=True)
    bnf_paragraph_code = models.CharField(max_length=7, blank=True, null=True)
    bnf_paragraph_name = models.CharField(max_length=255, blank=True, null=True)
    bnf_chemical_substance = models.CharField(max_length=255, blank=True, null=True)
    bnf_presentation_description = models.CharField(max_length=500, blank=True, null=True)
    bnf_version = models.CharField(max_length=50, blank=True, null=True)
    valid_from_date = models.DateField(blank=True, null=True)
    valid_to_date = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "BNF Hierarchy"
        verbose_name_plural = "BNF Hierarchies"

    def __str__(self):
        return f"{self.bnf_code_15digit} - {self.bnf_presentation_description or 'No Description'}"

    # --- ADD THIS PROPERTY FOR BNF_Full_Classification ---
    @property
    def full_classification(self):
        parts = []
        if self.bnf_chapter_name:
            parts.append(self.bnf_chapter_name)
        if self.bnf_section_name:
            parts.append(self.bnf_section_name)
        if self.bnf_paragraph_name:
            parts.append(self.bnf_paragraph_name)
        return " > ".join(parts) if parts else "N/A"


# --- 3. Medication_Products Table (Core Entity) ---
class MedicationProduct(models.Model):
    product_name = models.CharField(max_length=255, blank=True, null=True)
    npc_code = models.CharField(max_length=50, unique=True, blank=True, null=True)

    bnf_code_15digit = models.ForeignKey(
        BNFHierarchy,
        on_delete=models.PROTECT,
        related_name='medication_products_bnf',
        blank=True, null=True
    )
    chemical_name = models.ForeignKey(
        ChemicalComposition,
        on_delete=models.PROTECT,
        to_field='chemical_name',
        related_name='medication_products_chemical',
        blank=True, null=True
    )
    latest_average_price_gbp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # cost_effectiveness_status = models.CharField(max_length=100, null=True, blank=True) # <--- REMOVE THIS LINE

    class Meta:
        verbose_name = "Medication Product"
        verbose_name_plural = "Medication Products"

    def __str__(self):
        if self.product_name:
            return self.product_name
        elif self.npc_code:
            return f"Product (NPC: {self.npc_code})"
        elif self.bnf_code_15digit_id:
            return f"Product (BNF: {self.bnf_code_15digit_id})"
        return f"Product ID: {self.id}"

    # --- Add property for Annual_Usage_Estimate_Items (derived from pricing history) ---
    @property
    def annual_usage_estimate_items(self):
        # This will sum usage_estimate from all eMIT pricing records for this product
        # You might want to refine this to only sum for a specific year/period
        total_usage = self.pricing_history.filter(source='eMIT Hospital Data').aggregate(
            total_items=models.Sum('usage_estimate')
        )['total_items']
        return total_usage if total_usage is not None else 0


# --- 4. Medication_Pricing_History Table ---
class MedicationPricingHistory(models.Model):
    product = models.ForeignKey(
        MedicationProduct,
        on_delete=models.CASCADE,
        related_name='pricing_history'
    )
    source = models.CharField(max_length=255)
    price_gbp = models.DecimalField(max_digits=10, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    usage_estimate = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    price_change_measure = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Medication Pricing History"
        verbose_name_plural = "Medication Pricing Histories"
        ordering = ['-period_start']

    def __str__(self):
        return f"Price for {self.product.product_name if self.product.product_name else self.product.npc_code} from {self.source} ({self.period_start} to {self.period_end}): £{self.price_gbp}"

# --- CostEffectivenessAppraisal Table is REMOVED ---