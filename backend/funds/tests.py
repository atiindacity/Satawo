# funds/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import UserFund, DepositBatch, LedgerEntry
from .services import deposit_to_user, reserve_withdraw_fifo, transfer_liquid, reserve_to_liquid_self
from django.db import transaction

User = get_user_model()

class FundsFIFOTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username='alice', password='pass')
        self.bob = User.objects.create_user(username='bob', password='pass')
        # ensure funds objects exist
        UserFund.objects.create(user=self.alice)
        UserFund.objects.create(user=self.bob)

    def test_deposit_and_reserve_balance(self):
        deposit_to_user(self.alice, Decimal('1000.00'), 'reserve')
        uf = self.alice.funds
        self.assertEqual(uf.reserve_balance, Decimal('1000.00'))
        batches = DepositBatch.objects.filter(owner=self.alice, bucket='reserve')
        self.assertEqual(batches.count(), 1)
        batch = batches.first()
        self.assertEqual(batch.remaining_amount, Decimal('1000.00'))

    def test_fifo_withdraw_across_batches(self):
        # create 3 matured batches for alice
        b1 = deposit_to_user(self.alice, Decimal('500.00'), 'reserve')
        b2 = deposit_to_user(self.alice, Decimal('300.00'), 'reserve')
        b3 = deposit_to_user(self.alice, Decimal('200.00'), 'reserve')
        # mark matured True (simulate >1yr)
        DepositBatch.objects.update(matured=True)
        self.alice.funds.refresh_from_db()
        self.assertEqual(self.alice.funds.reserve_balance, Decimal('1000.00'))

        # withdraw 650 -> should consume 500 from b1 then 150 from b2
        consumption = reserve_withdraw_fifo(self.alice, Decimal('650.00'))
        self.alice.funds.refresh_from_db()
        # reserve_balance decreased
        self.assertEqual(self.alice.funds.reserve_balance, Decimal('350.00'))
        # check batch remaining_amounts
        b1.refresh_from_db()
        b2.refresh_from_db()
        b3.refresh_from_db()
        self.assertEqual(b1.remaining_amount, Decimal('0.00'))
        self.assertEqual(b2.remaining_amount, Decimal('150.00'))
        self.assertEqual(b3.remaining_amount, Decimal('200.00'))
        # ledger entries created (one for each consumed chunk)
        ledger = LedgerEntry.objects.filter(user=self.alice, entry_type='withdraw')
        self.assertEqual(ledger.count(), 2)

    def test_insufficient_matured_reserve_raises(self):
        deposit_to_user(self.alice, Decimal('100.00'), 'reserve')
        DepositBatch.objects.update(matured=False)  # not matured
        with self.assertRaisesMessage(ValueError, 'Insufficient matured reserve funds'):
            reserve_withdraw_fifo(self.alice, Decimal('50.00'))

    def test_liquid_transfer(self):
        # deposit liquid to alice
        deposit_to_user(self.alice, Decimal('1000.00'), 'liquid')
        deposit_to_user(self.bob, Decimal('100.00'), 'liquid')
        # transfer 200 from alice -> bob
        transfer_liquid(self.alice, self.bob, Decimal('200.00'))
        self.alice.funds.refresh_from_db()
        self.bob.funds.refresh_from_db()
        self.assertEqual(self.alice.funds.liquid_balance, Decimal('800.00'))
        self.assertEqual(self.bob.funds.liquid_balance, Decimal('300.00'))
        # ledger entries
        out = LedgerEntry.objects.filter(user=self.alice, entry_type='transfer_out')
        inn = LedgerEntry.objects.filter(user=self.bob, entry_type='transfer_in')
        self.assertEqual(out.count(), 1)
        self.assertEqual(inn.count(), 1)

    def test_atomicity_on_error(self):
        # deposit a reserve matured batch
        deposit_to_user(self.alice, Decimal('500.00'), 'reserve')
        DepositBatch.objects.update(matured=True)
        self.alice.funds.refresh_from_db()
        # simulate error by trying to reserve_withdraw more than matured
        initial_balance = self.alice.funds.reserve_balance
        with self.assertRaises(ValueError):
            reserve_withdraw_fifo(self.alice, Decimal('1000.00'))
        # balances should be unchanged
        self.alice.funds.refresh_from_db()
        self.assertEqual(self.alice.funds.reserve_balance, initial_balance)
