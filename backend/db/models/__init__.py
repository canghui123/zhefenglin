"""Import all models so Alembic autogenerate can discover them."""
from db.models.car_model import CarModel  # noqa: F401
from db.models.valuation import ValuationCache, DepreciationCache  # noqa: F401
from db.models.asset_package import AssetPackage, Asset  # noqa: F401
from db.models.sandbox import SandboxResult  # noqa: F401
from db.models.portfolio import (  # noqa: F401
    PortfolioSnapshot,
    AssetSegment,
    SegmentMetric,
    StrategyRun,
    CashflowBucket,
    ManagementGoal,
    RecommendedAction,
)
