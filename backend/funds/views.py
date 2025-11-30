

# backend/funds/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from .serializers import DepositSerializer, TransferSerializer
from .services import deposit_to_user, transfer_liquid, reserve_to_liquid_self, get_or_create_userfund
from django.contrib.auth import get_user_model
from .permissions import CanDepositToOthers, IsAdminOrStore
from .permissions import CanDeposit, CanTransferReserve


User = get_user_model()

@api_view(['POST'])
@permission_classes([IsAuthenticated, CanDepositToOthers])
def deposit_view(request):
    """
    POST /api/funds/deposit/
    body: { amount: Decimal, bucket: 'reserve'|'liquid', target_user_id (optional) }
    - If target_user_id is provided and != request.user.id -> only Admin/Store allowed (enforced by CanDepositToOthers)
    - If target_user_id omitted -> deposit to request.user
    """
    serializer = DepositSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    amount = Decimal(serializer.validated_data['amount'])
    bucket = serializer.validated_data['bucket']
    permission_classes = [IsAuthenticated, CanDeposit]


    target_id = request.data.get('target_user_id') or request.data.get('user_id') or None
    if target_id:
        try:
            target_user = User.objects.get(pk=int(target_id))
        except User.DoesNotExist:
            return Response({"detail": "Target user not found"}, status=status.HTTP_404_NOT_FOUND)
    else:
        target_user = request.user

    # If depositor is not admin/store and they try to deposit to someone else, CanDepositToOthers would have blocked already.

    try:
        deposit_to_user(target_user, amount, bucket, source=f'api_by_{request.user.id}')
    except Exception as e:
        return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"status": "ok", "amount": str(amount), "bucket": bucket, "target_user": target_user.id}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transfer_view(request):
    """
    POST /api/funds/transfer/
    body for liquid transfer: { to_user_id, amount, from_bucket: 'liquid' }
    body for reserve->liquid (self only): { amount, from_bucket: 'reserve' }
    Rules enforced:
      - Liquid transfers between users: allowed for any authenticated user (they can send liquid to others).
      - Reserve -> Liquid: only allowed for the owner (request.user) to convert their own matured reserve to liquid.
      - Reserve -> Liquid for others is forbidden.
    """
    serializer = TransferSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    amount = Decimal(serializer.validated_data['amount'])
    from_bucket = serializer.validated_data['from_bucket']

    if from_bucket == 'liquid':
        to_user_id = serializer.validated_data.get('to_user_id') or request.data.get('to_user_id')
        if not to_user_id:
            return Response({"detail": "to_user_id is required for liquid transfers"}, status=status.HTTP_400_BAD_REQUEST)
        recipient = User.objects.filter(pk=to_user_id).first()
        if not recipient:
            return Response({"detail": "Recipient not found"}, status=status.HTTP_404_NOT_FOUND)
        if recipient.pk == request.user.pk:
            return Response({"detail": "To transfer to self use reserve->liquid or skip transfer"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transfer_liquid(request.user, recipient, amount)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "ok", "transferred": str(amount), "to_user": recipient.id})

    elif from_bucket == 'reserve':
        # reserve->liquid must always be performed by the owner on their own account
        # (we disallow converting someone else's reserve to liquid)
        target_id = request.data.get('to_user_id') or request.data.get('target_user_id') or None
        if target_id and str(int(target_id)) != str(request.user.pk):
            return Response({"detail": "Cannot convert reserve->liquid for other users"}, status=status.HTTP_403_FORBIDDEN)

        try:
            consumption = reserve_to_liquid_self(request.user, amount)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "ok", "moved_from_reserve": str(amount), "consumption": consumption})

    else:
        return Response({"detail": "Unsupported bucket"}, status=status.HTTP_400_BAD_REQUEST)
