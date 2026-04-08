"""Legacy SQLite access layer (Task 1 MVP).

DEPRECATED: This module is kept only as a compatibility shim while
existing services and tests still talk raw sqlite3. The commercial DB
layer lives in `backend/db/` (SQLAlchemy 2.0) and schema is owned by
Alembic migrations under `backend/alembic/versions/`.

Do not extend this file with new tables. Add new persistence via the
SQLAlchemy models in `backend/db/models/` and a new Alembic revision.
"""
import sqlite3
import os
from config import settings

def get_db_path():
    return settings.database_path

def get_connection():
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS car_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            che300_model_id TEXT UNIQUE NOT NULL,
            brand TEXT NOT NULL,
            series TEXT NOT NULL,
            model_name TEXT NOT NULL,
            year INTEGER,
            displacement TEXT,
            fuel_type TEXT,
            guide_price REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS valuation_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            che300_model_id TEXT NOT NULL,
            registration_date TEXT NOT NULL,
            query_date TEXT NOT NULL,
            city_code TEXT,
            excellent_price REAL,
            good_price REAL,
            medium_price REAL,
            fair_price REAL,
            dealer_buy_price REAL,
            dealer_sell_price REAL,
            raw_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(che300_model_id, registration_date, query_date, city_code)
        );

        CREATE TABLE IF NOT EXISTS asset_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            upload_filename TEXT,
            total_assets INTEGER DEFAULT 0,
            parameters_json TEXT,
            results_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER REFERENCES asset_packages(id) ON DELETE CASCADE,
            row_number INTEGER,
            car_description TEXT,
            vin TEXT,
            first_registration TEXT,
            gps_online INTEGER,
            insurance_lapsed INTEGER,
            ownership_transferred INTEGER,
            loan_principal REAL,
            buyout_price REAL,
            matched_model_id TEXT,
            che300_valuation REAL,
            depreciation_30d REAL,
            depreciation_60d REAL,
            total_cost REAL,
            expected_revenue REAL,
            net_profit REAL,
            risk_flags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS depreciation_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT NOT NULL,
            valuation REAL,
            prediction_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sandbox_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_description TEXT,
            entry_date TEXT,
            overdue_amount REAL,
            che300_value REAL,
            daily_parking REAL,
            input_json TEXT,
            path_a_json TEXT,
            path_b_json TEXT,
            path_c_json TEXT,
            path_d_json TEXT,
            path_e_json TEXT,
            recommendation TEXT,
            best_path TEXT,
            report_pdf_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id TEXT DEFAULT 'default',
            snapshot_date TEXT NOT NULL,
            scenario_name TEXT DEFAULT 'baseline',
            total_ead REAL DEFAULT 0,
            total_book_value REAL DEFAULT 0,
            total_expected_loss REAL DEFAULT 0,
            total_expected_loss_rate REAL DEFAULT 0,
            total_expected_cash_30d REAL DEFAULT 0,
            total_expected_cash_90d REAL DEFAULT 0,
            total_expected_cash_180d REAL DEFAULT 0,
            total_provision_impact REAL DEFAULT 0,
            total_capital_impact REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS asset_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id TEXT DEFAULT 'default',
            name TEXT NOT NULL,
            overdue_bucket TEXT,
            recovered_status TEXT,
            inventory_bucket TEXT,
            legal_completeness TEXT,
            vehicle_type TEXT,
            region TEXT,
            custom_rules_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS segment_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER REFERENCES portfolio_snapshots(id),
            segment_id INTEGER REFERENCES asset_segments(id),
            asset_count INTEGER DEFAULT 0,
            total_ead REAL DEFAULT 0,
            avg_vehicle_value REAL DEFAULT 0,
            avg_lgd REAL DEFAULT 0,
            avg_recovery_days INTEGER DEFAULT 0,
            expected_loss_amount REAL DEFAULT 0,
            expected_loss_rate REAL DEFAULT 0,
            expected_cash_30d REAL DEFAULT 0,
            expected_cash_90d REAL DEFAULT 0,
            expected_cash_180d REAL DEFAULT 0,
            recommended_strategy TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS strategy_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER REFERENCES portfolio_snapshots(id),
            segment_id INTEGER REFERENCES asset_segments(id),
            strategy_type TEXT NOT NULL,
            success_probability REAL DEFAULT 0,
            expected_recovery_gross REAL DEFAULT 0,
            towing_cost REAL DEFAULT 0,
            inventory_cost REAL DEFAULT 0,
            legal_cost REAL DEFAULT 0,
            refurbishment_cost REAL DEFAULT 0,
            channel_fee REAL DEFAULT 0,
            funding_cost REAL DEFAULT 0,
            management_cost REAL DEFAULT 0,
            discount_cost REAL DEFAULT 0,
            net_recovery_pv REAL DEFAULT 0,
            expected_loss_amount REAL DEFAULT 0,
            expected_loss_rate REAL DEFAULT 0,
            expected_recovery_days INTEGER DEFAULT 0,
            capital_release_score REAL DEFAULT 0,
            notes_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS cashflow_buckets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_run_id INTEGER REFERENCES strategy_runs(id),
            bucket_day INTEGER NOT NULL,
            gross_cash_in REAL DEFAULT 0,
            gross_cash_out REAL DEFAULT 0,
            net_cash_flow REAL DEFAULT 0,
            discounted_net_cash_flow REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS management_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id TEXT DEFAULT 'default',
            period_type TEXT DEFAULT 'month',
            role_level TEXT DEFAULT 'manager',
            goal_name TEXT NOT NULL,
            goal_category TEXT,
            target_value REAL DEFAULT 0,
            target_unit TEXT,
            baseline_value REAL DEFAULT 0,
            confidence_level REAL DEFAULT 0,
            constraint_notes TEXT,
            owner_id TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS recommended_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id INTEGER REFERENCES portfolio_snapshots(id),
            role_level TEXT NOT NULL,
            segment_id INTEGER,
            strategy_type TEXT,
            recommendation_title TEXT NOT NULL,
            recommendation_text TEXT,
            expected_loss_impact REAL DEFAULT 0,
            expected_cashflow_impact REAL DEFAULT 0,
            expected_inventory_impact REAL DEFAULT 0,
            feasibility_score REAL DEFAULT 0,
            realism_score REAL DEFAULT 0,
            resource_need_json TEXT,
            approval_level TEXT,
            priority INTEGER DEFAULT 3,
            dependencies_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
