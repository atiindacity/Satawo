Security design notes (high level):
- Password hashing: Django configured to use Argon2 if installed (see requirements).
- Sensitive fields encryption: uses Fernet symmetric encryption in settings (FERNET_KEY).
- JWT with rotation & expiry implemented using djangorestframework-simplejwt.
- File upload: random filenames; ensure virus scanning hook before saving in production.
- Audit log: LedgerEntry is append-only and immutable flag set to True.
- Reserve FIFO logic: DepositBatch tracks created_at and withdrawals should consume oldest batches.
