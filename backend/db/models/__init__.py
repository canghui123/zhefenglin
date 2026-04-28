"""Import all models so Alembic autogenerate can discover them."""
from db.models.car_model import CarModel  # noqa: F401
from db.models.valuation import ValuationCache, DepreciationCache  # noqa: F401
from db.models.asset_package import AssetPackage, Asset  # noqa: F401
from db.models.sandbox import (  # noqa: F401
    SandboxResult,
    SandboxSimulationBatch,
    SandboxSimulationBatchItem,
)
from db.models.portfolio import (  # noqa: F401
    PortfolioSnapshot,
    AssetSegment,
    SegmentMetric,
    StrategyRun,
    CashflowBucket,
    ManagementGoal,
    RecommendedAction,
)
from db.models.tenant import Tenant  # noqa: F401
from db.models.user import User  # noqa: F401
from db.models.user_session import UserSession  # noqa: F401
from db.models.membership import Membership  # noqa: F401
from db.models.audit_log import AuditLog  # noqa: F401
from db.models.job_run import JobRun  # noqa: F401
from db.models.decision_model_config import (  # noqa: F401
    BrandRetentionProfile,
    RegionDisposalCoefficient,
)
from db.models.work_order import WorkOrder  # noqa: F401
from db.models.model_feedback import DisposalOutcome, ModelLearningRun  # noqa: F401
from db.models.data_import import DataImportBatch, DataImportRow  # noqa: F401
