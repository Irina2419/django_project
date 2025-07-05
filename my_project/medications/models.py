# medications/models.py

from django.db import models

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
    bnf_chapter_code = models.CharField(max_length=2, blank=True, null=True) # Make nullable for flexibility
    bnf_chapter_name = models.CharField(max_length=255, blank=True, null=True) # Make nullable
    bnf_section_code = models.CharField(max_length=5, blank=True, null=True) # Make nullable
    bnf_section_name = models.CharField(max_length=255, blank=True, null=True) # Make nullable
    bnf_paragraph_code = models.CharField(max_length=7, blank=True, null=True) # Make nullable
    bnf_paragraph_name = models.CharField(max_length=255, blank=True, null=True) # Make nullable
    bnf_chemical_substance = models.CharField(max_length=255, blank=True, null=True) # Make nullable
    bnf_presentation_description = models.CharField(max_length=500, blank=True, null=True) # Make nullable
    bnf_version = models.CharField(max_length=50, blank=True, null=True) # Make nullable
    valid_from_date = models.DateField(blank=True, null=True) # Make nullable
    valid_to_date = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = "BNF Hierarchy"
        verbose_name_plural = "BNF Hierarchies"

    def __str__(self):
        return f"{self.bnf_code_15digit} - {self.bnf_presentation_description or 'No Description'}"

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
    cost_effectiveness_status = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Medication Product"
        verbose_name_plural = "Medication Products"

    def __str__(self):
        # Make __str__ more robust to avoid errors if fields are None
        if self.product_name:
            return self.product_name
        elif self.npc_code:
            return f"Product (NPC: {self.npc_code})"
        elif self.bnf_code_15digit_id: # Check if BNF is linked by its ID
            return f"Product (BNF: {self.bnf_code_15digit_id})"
        return f"Product ID: {self.id}" # Fallback to Django's auto-generated ID

# --- 4. Medication_Pricing_History Table ---
class MedicationPricingHistory(models.Model):
    # PriceRecordID (Primary Key - Django automatically creates 'id' as PK by default)
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
    # --- INCREASED max_digits for price_change_measure ---
    price_change_measure = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = "Medication Pricing History"
        verbose_name_plural = "Medication Pricing Histories"
        ordering = ['-period_start']

    def __str__(self):
        return f"Price for {self.product.product_name} from {self.source} ({self.period_start} to {self.period_end}): £{self.price_gbp}"

# --- 5. Cost_Effectiveness_Appraisals Table ---
class CostEffectivenessAppraisal(models.Model):
    # AppraisalID (Primary Key - Django automatically creates 'id' as PK by default)
    product = models.ForeignKey(
        MedicationProduct,
        on_delete=models.CASCADE, # If product is deleted, delete its appraisals
        related_name='cost_effectiveness_appraisals'
    )
    nice_guidance_id = models.CharField(max_length=100, blank=True, null=True) # e.g., 'TA312'
    recommendation_status = models.CharField(max_length=100) # e.g., 'Recommended', 'Not Recommended'
    icer_gbp_per_qaly = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True) # Increased max_digits for ICER
    appraisal_date = models.DateField()
    summary_of_findings = models.TextField(blank=True, null=True)
    rationale_for_decision = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Cost Effectiveness Appraisal"
        verbose_name_plural = "Cost Effectiveness Appraisals"
        ordering = ['-appraisal_date'] # Order by most recent appraisal first

    def __str__(self):
        return f"Appraisal for {self.product.product_name}: {self.recommendation_status} ({self.appraisal_date})"