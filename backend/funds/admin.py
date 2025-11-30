from django.contrib import admin
from .models import DepositBatch, LedgerEntry
admin.site.register(DepositBatch)
admin.site.register(LedgerEntry)
