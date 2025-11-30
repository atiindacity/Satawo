

# funds/models.py
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model

User = get_user_model()

class UserFund(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='funds')
    reserve_balance = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))
    liquid_balance = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"Funds({self.user.username}): reserve={self.reserve_balance} liquid={self.liquid_balance}"

class DepositBatch(models.Model):
    BUCKET_CHOICES = (
        ('reserve', 'Reserve'),
        ('liquid', 'Liquid'),
    )

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposit_batches')
    amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    remaining_amount = models.DecimalField(max_digits=20, decimal_places=2)
    bucket = models.CharField(max_length=10, choices=BUCKET_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    matured = models.BooleanField(default=False)
    matured_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('created_at',)

    def save(self, *args, **kwargs):
        if not self.pk:
            # on creation, remaining_amount defaults to full amount
            if self.remaining_amount is None:
                self.remaining_amount = self.amount
            # set matured_at to created_at + 365 days (not automatically matured)
            self.matured_at = timezone.now() + timezone.timedelta(days=365)
            self.matured = False
        super().save(*args, **kwargs)

    def consume(self, amount):
        """
        Deduct amount from this batch's remaining_amount and return the consumed amount.
        Assumes caller holds select_for_update lock if concurrency-critical.
        """
        if amount <= 0:
            return Decimal('0.00')
        available = self.remaining_amount
        to_consume = min(available, amount)
        self.remaining_amount = (self.remaining_amount - to_consume).quantize(Decimal('0.01'))
        self.save(update_fields=['remaining_amount'])
        return to_consume

class LedgerEntry(models.Model):
    # type examples: deposit, withdraw, transfer_out, transfer_in, fee, interest
    ENTRY_TYPES = (
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('transfer_out', 'Transfer Out'),
        ('transfer_in', 'Transfer In'),
        ('fee', 'Fee'),
        ('interest', 'Interest'),
        ('reserve_to_liquid', 'Reserve -> Liquid'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ledger_entries')
    entry_type = models.CharField(max_length=30, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    bucket = models.CharField(max_length=10, choices=DepositBatch.BUCKET_CHOICES, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
    related_batch = models.ForeignKey(DepositBatch, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ('-timestamp',)
