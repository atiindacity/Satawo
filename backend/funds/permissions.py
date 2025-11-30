# backend/funds/permissions.py
from rest_framework import permissions

class IsAdminOrStore(permissions.BasePermission):
    """
    Allow access only to users with role 'admin' or 'store'.
    Use this for endpoints where only Admins or Stores may deposit to *other* users.
    """
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, 'role', None) in ('admin', 'store'))

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Allow if the user is acting on their own resource OR is admin.
    Use for reserve->liquid (self only) or read/update on own resources.
    """
    def has_object_permission(self, request, view, obj):
        # obj is expected to be a user instance in some views
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if getattr(user, 'role', None) == 'admin':
            return True
        # assume obj is a user instance
        return getattr(obj, 'pk', None) == getattr(user, 'pk', None)

class CanDepositToOthers(permissions.BasePermission):
    """
    For deposit endpoint: allow Admin and Store to deposit to other users.
    If depositing to self, any authenticated user may deposit to their own liquid (or maybe not - you can change policy).
    We'll enforce: deposit to other user => only Admin/Store; deposit to self => authenticated allowed.
    The view must set 'target_user' on the view (or pass in request.data['target_user_id']).
    """
    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        # Determine target user id from request data (common patterns)
        target_id = request.data.get('user_id') or request.data.get('target_user_id') or request.data.get('to_user_id')
        if target_id is None:
            # default: if not specified, target is current user => allow
            return True

        try:
            # if they are depositing to someone else (id != current user id)
            if str(target_id) != str(getattr(user, 'pk')):
                return getattr(user, 'role', None) in ('admin', 'store')
            return True
        except Exception:
            return False

from rest_framework.permissions import BasePermission

class CanDeposit(BasePermission):
    def has_permission(self, request, view):
        # user must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # regular user depositing to self only
        if request.method == "POST" and view.action == "deposit":
            target = request.data.get("user")
            return str(request.user.id) == str(target) or request.user.role in ["admin", "store"]

        return True


class CanTransferReserve(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # only owner can move reserve -> liquid
        target = view.kwargs.get("user_id")
        return str(request.user.id) == str(target)
