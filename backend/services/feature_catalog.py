"""Central feature flag catalog used by runtime gating and admin tooling."""
from __future__ import annotations

FEATURE_CATALOG: tuple[dict[str, str], ...] = (
    {
        "key": "dashboard.advanced",
        "label": "高级成本中心",
        "category": "analytics",
        "description": "解锁成本中心总览与高级经营指标。",
    },
    {
        "key": "audit.export",
        "label": "审计导出",
        "category": "governance",
        "description": "允许导出 CSV、报告打印和审计留档相关动作。",
    },
    {
        "key": "deployment.private_config",
        "label": "私有化配置",
        "category": "deployment",
        "description": "允许管理私有化部署、专属交付与环境配置能力。",
    },
    {
        "key": "portfolio.advanced_pages",
        "label": "高级驾驶舱页面",
        "category": "portfolio",
        "description": "开放高管驾驶页与经理作战手册等高级页面。",
    },
    {
        "key": "routing.model_control",
        "label": "模型路由控制",
        "category": "ai",
        "description": "允许查看和调整模型路由策略与高成本模式。",
    },
    {
        "key": "tenant.value_dashboard",
        "label": "租户价值看板",
        "category": "commercial",
        "description": "开放面向销售与续费沟通的价值看板。",
    },
    {
        "key": "pricing.custom_quote",
        "label": "自定义报价",
        "category": "commercial",
        "description": "允许使用私有报价与定制商务配置。",
    },
)

FEATURE_KEYS: tuple[str, ...] = tuple(item["key"] for item in FEATURE_CATALOG)
FEATURE_INDEX: dict[str, dict[str, str]] = {item["key"]: item for item in FEATURE_CATALOG}

