# funds/services.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import UserFund, DepositBatch, LedgerEntry
from django.contrib.auth import get_user_model
from django.db.models import F

User = get_user_model()

def get_or_create_userfund(user):
    uf, _ = UserFund.objects.get_or_create(user=user)
    return uf

def create_ledger_entry(user, entry_type, amount, bucket=None, metadata=None, related_batch=None):
    if metadata is None:
        metadata = {}
    return LedgerEntry.objects.create(
        user=user,
        entry_type=entry_type,
        amount=amount,
        bucket=bucket,
        metadata=metadata,
        related_batch=related_batch
    )

@transaction.atomic
def deposit_to_user(user, amount: Decimal, bucket: str, source='store'):
    """
    Atomic deposit. Creates a DepositBatch for reserve, direct balance change for liquid.
    Records ledger entry.
    """
    if amount <= Decimal('0.00'):
        raise ValueError("Deposit amount must be positive")

    uf = get_or_create_userfund(user)
    # get a db lock on the userfund row
    uf = UserFund.objects.select_for_update().get(pk=uf.pk)

    if bucket == 'reserve':
        batch = DepositBatch.objects.create(
            owner=user,
            amount=amount,
            remaining_amount=amount,
            bucket='reserve',
        )
        # increase reserve balance
        uf.reserve_balance = (uf.reserve_balance + amount).quantize(Decimal('0.01'))
        uf.save(update_fields=['reserve_balance'])
        # ledger entry pointing to batch
        create_ledger_entry(user=user, entry_type='deposit', amount=amount, bucket='reserve', metadata={'source': source}, related_batch=batch)
        return batch
    elif bucket == 'liquid':
        uf.liquid_balance = (uf.liquid_balance + amount).quantize(Decimal('0.01'))
        uf.save(update_fields=['liquid_balance'])
        create_ledger_entry(user=user, entry_type='deposit', amount=amount, bucket='liquid', metadata={'source': source})
        return None
    else:
        raise ValueError("Invalid bucket")

@transaction.atomic
def reserve_withdraw_fifo(user, amount: Decimal):
    """
    Withdraw amount from user's matured reserve batches using FIFO.
    Deducts remaining_amount from DepositBatch objects (select_for_update),
    creates ledger entries for each consumed segment, updates user's reserve_balance.
    Returns list of dicts describing consumption.
    """
    if amount <= Decimal('0.00'):
        raise ValueError("Withdraw amount must be positive")

    uf = get_or_create_userfund(user)
    uf = UserFund.objects.select_for_update().get(pk=uf.pk)

    if uf.reserve_balance < amount:
        raise ValueError("Insufficient reserve balance")

    # lock matured reserve batches with remaining > 0
    now = timezone.now()
    batches_qs = DepositBatch.objects.select_for_update().filter(
        owner=user,
        bucket='reserve',
        remaining_amount__gt=Decimal('0.00'),
        matured=True
    ).order_by('created_at')

    remaining = amount
    consumption = []

    for batch in batches_qs:
        if remaining <= Decimal('0.00'):
            break
        consumed = batch.consume(remaining)  # handles save
        if consumed > 0:
            create_ledger_entry(user=user, entry_type='withdraw', amount=consumed, bucket='reserve', metadata={'batch_id': batch.id})
            consumption.append({'batch_id': batch.id, 'consumed': str(consumed)})
            remaining = (remaining - consumed).quantize(Decimal('0.01'))

    if remaining > Decimal('0.00'):
        # couldn't satisfy requested amount from matured batches
        raise ValueError("Insufficient matured reserve funds to complete withdrawal (FIFO)")

    # decrease user's reserve_balance
    uf.reserve_balance = (uf.reserve_balance - amount).quantize(Decimal('0.01'))
    uf.save(update_fields=['reserve_balance'])
    return consumption

@transaction.atomic
def transfer_liquid(sender, recipient, amount: Decimal):
    """
    Transfer liquid funds from sender to recipient atomically.
    Creates ledger entries for transfer_out and transfer_in.
    """
    if amount <= Decimal('0.00'):
        raise ValueError("Transfer amount must be positive")
    if sender.pk == recipient.pk:
        raise ValueError("Sender and recipient cannot be the same for liquid transfer")

    sender_uf = get_or_create_userfund(sender)
    recipient_uf = get_or_create_userfund(recipient)

    # lock both rows; order by pk to avoid deadlocks
    if sender_uf.pk < recipient_uf.pk:
        sender_uf = UserFund.objects.select_for_update().get(pk=sender_uf.pk)
        recipient_uf = UserFund.objects.select_for_update().get(pk=recipient_uf.pk)
    else:
        recipient_uf = UserFund.objects.select_for_update().get(pk=recipient_uf.pk)
        sender_uf = UserFund.objects.select_for_update().get(pk=sender_uf.pk)

    if sender_uf.liquid_balance < amount:
        raise ValueError("Insufficient liquid balance")

    # update balances
    sender_uf.liquid_balance = (sender_uf.liquid_balance - amount).quantize(Decimal('0.01'))
    recipient_uf.liquid_balance = (recipient_uf.liquid_balance + amount).quantize(Decimal('0.01'))
    sender_uf.save(update_fields=['liquid_balance'])
    recipient_uf.save(update_fields=['liquid_balance'])

    create_ledger_entry(user=sender, entry_type='transfer_out', amount=amount, bucket='liquid', metadata={'to_user_id': recipient.id})
    create_ledger_entry(user=recipient, entry_type='transfer_in', amount=amount, bucket='liquid', metadata={'from_user_id': sender.id})

    return True

@transaction.atomic
def reserve_to_liquid_self(user, amount: Decimal):
    """
    Move funds from user's reserve (FIFO) into user's liquid balance atomically.
    This will consume matured reserve batches FIFO and credit user's liquid balance.
    """
    # withdraw from reserve FIFO (this will create withdraw ledger entries per batch)
    consumption = reserve_withdraw_fifo(user, amount)
    # now credit user's liquid balance
    uf = get_or_create_userfund(user)
    uf = UserFund.objects.select_for_update().get(pk=uf.pk)
    uf.liquid_balance = (uf.liquid_balance + amount).quantize(Decimal('0.01'))
    uf.save(update_fields=['liquid_balance'])
    create_ledger_entry(user=user, entry_type='reserve_to_liquid', amount=amount, bucket='liquid', metadata={'consumption': consumption})
    return consumption
