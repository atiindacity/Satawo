# backend/funds/tests_rbac.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from rest_framework.test import APIClient
from .models import UserFund, DepositBatch
from .services import deposit_to_user

User = get_user_model()

class RBACDepositTransferTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(...)
        self.store = User.objects.create_user(...)
        self.user1 = User.objects.create_user(...)

        self.client.force_authenticate(user=self.admin)

    def test_store_can_deposit_to_other_user(self):
        self.client.login(username='store', password='pass')
        resp = self.client.post('/api/funds/deposit/', data={'amount': '100.00', 'bucket': 'liquid', 'target_user_id': self.alice.id}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.alice.funds.refresh_from_db()
        self.assertEqual(self.alice.funds.liquid_balance, Decimal('100.00'))

    def test_regular_user_cannot_deposit_to_other_user(self):
        self.client.login(username='alice', password='pass')
        resp = self.client.post('/api/funds/deposit/', data={'amount': '50.00', 'bucket': 'liquid', 'target_user_id': self.bob.id}, format='json')
        # should be forbidden by CanDepositToOthers
        self.assertIn(resp.status_code, (403, 400))  # 403 preferred

    def test_regular_user_can_deposit_to_self(self):
        self.client.login(username='alice', password='pass')
        resp = self.client.post('/api/funds/deposit/', data={'amount': '25.00', 'bucket': 'liquid'}, format='json')
        self.assertEqual(resp.status_code, 201)
        self.alice.funds.refresh_from_db()
        self.assertEqual(self.alice.funds.liquid_balance, Decimal('25.00'))

    def test_reserve_to_liquid_only_owner(self):
        # create matured reserve batch for alice
        deposit_to_user(self.alice, Decimal('200.00'), 'reserve')
        DepositBatch.objects.filter(owner=self.alice).update(matured=True)
        self.client.login(username='bob', password='pass')
        # bob trying to convert alice's reserve -> liquid (forbidden)
        resp = self.client.post('/api/funds/transfer/', data={'amount': '100', 'from_bucket': 'reserve', 'to_user_id': self.alice.id}, format='json')
        self.assertEqual(resp.status_code, 403)

        # alice converts her own reserve -> liquid
        self.client.login(username='alice', password='pass')
        resp2 = self.client.post('/api/funds/transfer/', data={'amount': '100', 'from_bucket': 'reserve'}, format='json')
        self.assertEqual(resp2.status_code, 200)
