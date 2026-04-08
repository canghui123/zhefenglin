"""Repository layer — the only component allowed to talk to the DB directly.

All modules under `api/` and the DB-touching services (che300_client,
depreciation) must go through these functions instead of raw SQL.
"""
