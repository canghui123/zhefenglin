export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  code: string;
  requestId: string;
  details: unknown;
  constructor(
    message: string,
    status: number,
    code: string = "",
    requestId: string = "",
    details: unknown = null,
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

async function buildApiError(
  res: Response,
  fallbackMessage: string = "请求失败",
): Promise<ApiError> {
  const body = await res.json().catch(() => ({ detail: res.statusText }));
  if (body?.error?.code) {
    return new ApiError(
      body.error.message || fallbackMessage,
      res.status,
      body.error.code,
      body.error.request_id || "",
      body.error.details || null,
    );
  }
  return new ApiError(body.detail || fallbackMessage, res.status);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    throw await buildApiError(res);
  }
  return res.json();
}

// 健康检查
export async function healthCheck() {
  return request<{ status: string }>("/api/health");
}

// 资产包上传
export async function uploadExcel(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{
    package_id: number;
    filename: string;
    parse_result: {
      assets: Array<{
        row_number: number;
        car_description: string;
        vin: string | null;
        first_registration: string | null;
        mileage: number | null;
        gps_online: boolean | null;
        insurance_lapsed: boolean | null;
        ownership_transferred: boolean | null;
        loan_principal: number | null;
        buyout_price: number | null;
      }>;
      errors: Array<{ row_number: number; field: string; message: string }>;
      total_rows: number;
      success_rows: number;
      column_mapping: Record<string, string>;
      unmapped_columns: string[];
      suggested_strategy: "direct" | "discount" | "ai_suggest";
      strategy_message: string;
    };
  }>("/api/asset-package/upload", { method: "POST", body: form });
}

// AI 买断价建议
export interface BuyoutSuggestion {
  row_number: number;
  car_description: string;
  first_registration: string | null;
  mileage: number | null;
  che300_valuation: number | null;
  suggested_buyout_low: number;
  suggested_buyout_mid: number;
  suggested_buyout_high: number;
}

export interface ApprovalContext {
  recommended: boolean;
  approval_type: string;
  reason: string;
  related_object_type: string | null;
  related_object_id: string | null;
  estimated_cost: number;
  metadata: Record<string, unknown>;
}

export interface SuggestBuyoutOptions {
  advanced_condition_pricing?: boolean;
  manual_selected?: boolean;
  approval_mode?: boolean;
  approval_request_id?: number | null;
  strict_policy?: boolean;
  single_task_budget?: number | null;
}

export async function suggestBuyout(
  packageId: number,
  vehicleCondition: string,
  options: SuggestBuyoutOptions = {},
) {
  return request<{
    package_id: number;
    vehicle_condition: string;
    total_suggested_buyout: number;
    suggestions: BuyoutSuggestion[];
    ai_comment: string;
  }>("/api/asset-package/suggest-buyout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      package_id: packageId,
      vehicle_condition: vehicleCondition,
      ...options,
    }),
  });
}

// 运行定价计算 (returns 202 with job reference)
export async function calculatePackage(
  packageId: number,
  parameters: PricingParameters,
  aiBuyoutOverrides?: Record<number, number>,
): Promise<{ job_id: number; status: string }> {
  const body: Record<string, unknown> = { package_id: packageId, parameters };
  if (aiBuyoutOverrides) body.ai_buyout_overrides = aiBuyoutOverrides;
  const res = await fetch(`${API_BASE}/api/asset-package/calculate`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok && res.status !== 202) {
    throw await buildApiError(res, "计算请求失败");
  }
  return res.json();
}

// 获取资产包结果
export async function getPackage(packageId: number) {
  return request<{ id: number; name: string; results: PackageCalculationResult | null }>(
    `/api/asset-package/${packageId}`
  );
}

// 资产包列表
export async function listPackages() {
  return request<Array<{ id: number; name: string; total_assets: number; created_at: string }>>(
    "/api/asset-package/list/all"
  );
}

// 沙盘模拟
export async function simulateSandbox(input: SandboxInput) {
  return request<SandboxResult>("/api/sandbox/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

// 生成报告 (returns 202 with job reference)
export async function generateReport(
  resultId: number
): Promise<{ job_id: number; status: string }> {
  const res = await fetch(`${API_BASE}/api/sandbox/${resultId}/report`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok && res.status !== 202) {
    throw new ApiError("报告生成失败", res.status);
  }
  return res.json();
}

// 下载已生成的报告HTML
export async function downloadReport(resultId: number): Promise<string> {
  const res = await fetch(
    `${API_BASE}/api/sandbox/${resultId}/report/download`,
    { credentials: "include" }
  );
  if (!res.ok) throw new ApiError("报告下载失败", res.status);
  return res.text();
}

// 沙盘结果列表
export async function listSandboxResults() {
  return request<
    Array<{ id: number; car_description: string; che300_value: number; recommendation: string; created_at: string }>
  >("/api/sandbox/list/all");
}

// ============ 经营驾驶舱 API ============

export async function getPortfolioOverview() {
  return request<PortfolioOverviewData>("/api/portfolio/overview");
}

export async function getSegmentation(dimension: string = "overdue_bucket") {
  return request<SegmentationData>(`/api/portfolio/segmentation?dimension=${dimension}`);
}

export async function getStrategies(segmentIndex: number = 0) {
  return request<StrategyData>(`/api/portfolio/strategies?segment_index=${segmentIndex}`);
}

export async function getCashflow() {
  return request<CashflowData>("/api/portfolio/cashflow");
}

export async function getExecutiveDashboard() {
  return request<ExecutiveData>("/api/portfolio/executive");
}

export async function getManagerPlaybook() {
  return request<ManagerData>("/api/portfolio/manager-playbook");
}

export async function getSupervisorConsole() {
  return request<SupervisorData>("/api/portfolio/supervisor-console");
}

export async function getActionCenter() {
  return request<ActionCenterData>("/api/portfolio/action-center");
}

// ============ 用户管理 API ============

export interface UserInfo {
  id: number;
  email: string;
  display_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export async function listUsers() {
  return request<UserInfo[]>("/api/admin/users");
}

export async function updateUserRole(userId: number, role: string) {
  return request<UserInfo>(`/api/admin/users/${userId}/role`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
}

export async function toggleUserActive(userId: number, isActive: boolean) {
  return request<UserInfo>(`/api/admin/users/${userId}/active`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_active: isActive }),
  });
}

// ============ 商业化管理 API ============

export interface CommercialPlan {
  id: number;
  code: string;
  name: string;
  billing_cycle_supported: string;
  monthly_price: number;
  yearly_price: number;
  setup_fee: number;
  private_deploy_fee: number;
  seat_limit: number;
  included_vin_calls: number;
  included_condition_pricing_points: number;
  included_ai_reports: number;
  included_asset_packages: number;
  included_sandbox_runs: number;
  overage_vin_unit_price: number;
  overage_condition_pricing_unit_price: number;
  feature_flags: Record<string, boolean>;
  is_active: boolean;
}

export interface CommercialPlanInput {
  code: string;
  name: string;
  billing_cycle_supported: string;
  monthly_price: number;
  yearly_price: number;
  setup_fee: number;
  private_deploy_fee: number;
  seat_limit: number;
  included_vin_calls: number;
  included_condition_pricing_points: number;
  included_ai_reports: number;
  included_asset_packages: number;
  included_sandbox_runs: number;
  overage_vin_unit_price: number;
  overage_condition_pricing_unit_price: number;
  feature_flags: Record<string, boolean>;
  is_active: boolean;
}

export interface TenantSubscriptionInfo {
  id: number;
  tenant_id: number;
  tenant_code: string | null;
  tenant_name: string | null;
  plan_code: string | null;
  plan_name: string | null;
  status: string;
  monthly_budget_limit: number;
  alert_threshold_percent: number;
}

export interface SubscriptionUpdateInput {
  plan_code: string;
  status: string;
  monthly_budget_limit: number;
  alert_threshold_percent: number;
}

export interface CostCenterOverview {
  month: string;
  tenant_count: number;
  active_subscription_count: number;
  totals: {
    vin_calls: number;
    condition_pricing_calls: number;
    llm_input_tokens: number;
    llm_output_tokens: number;
    llm_cost: number;
    che300_cost: number;
    total_cost: number;
    estimated_revenue: number;
    estimated_gross_profit: number;
  };
  modules: Array<{ module: string; events: number; quantity: number; cost: number }>;
}

export interface CostCenterTenantRow {
  tenant_id: number;
  tenant_code: string;
  tenant_name: string;
  plan_code: string | null;
  plan_name: string | null;
  vin_calls: number;
  condition_pricing_calls: number;
  llm_input_tokens: number;
  llm_output_tokens: number;
  total_cost: number;
  estimated_revenue: number;
  estimated_gross_profit: number;
  avg_cost_per_vehicle: number;
  monthly_budget_limit: number;
}

export interface ValueDashboardData {
  month: string;
  estimated_hours_saved: number;
  high_risk_vehicles: number;
  blocked_high_cost_calls: number;
  recommended_path_coverage: number;
  estimated_decisions_processed: number;
}

export interface ModelRoutingRule {
  id: number;
  scope: string;
  tenant_id: number | null;
  task_type: string;
  preferred_model: string;
  fallback_model: string | null;
  allow_batch: boolean;
  allow_search: boolean;
  allow_high_cost_mode: boolean;
  prompt_version: string;
  is_active: boolean;
}

export interface ModelRoutingRuleInput {
  scope: string;
  tenant_id?: number | null;
  task_type: string;
  preferred_model: string;
  fallback_model?: string | null;
  allow_batch: boolean;
  allow_search: boolean;
  allow_high_cost_mode: boolean;
  prompt_version: string;
  is_active: boolean;
}

export interface ValuationRule {
  id: number;
  scope: string;
  tenant_id: number | null;
  enabled: boolean;
  trigger_type: string;
  trigger_config: Record<string, unknown>;
}

export interface ValuationRuleInput {
  scope: string;
  tenant_id?: number | null;
  enabled: boolean;
  trigger_type: string;
  trigger_config: Record<string, unknown>;
}

export interface ApprovalRequestInfo {
  id: number;
  tenant_id: number;
  type: string;
  status: string;
  applicant_user_id: number;
  approver_user_id: number | null;
  reason: string;
  related_object_type: string | null;
  related_object_id: string | null;
  estimated_cost: number;
  actual_cost: number;
  metadata: Record<string, unknown>;
  created_at: string | null;
  decided_at: string | null;
  consumed_at: string | null;
  consumed_request_id: string | null;
  is_consumed: boolean;
}

export async function listCommercialPlans() {
  return request<CommercialPlan[]>("/api/admin/settings/plans");
}

export async function createCommercialPlan(input: CommercialPlanInput) {
  return request<CommercialPlan>("/api/admin/settings/plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function updateCommercialPlan(planId: number, input: Partial<CommercialPlanInput>) {
  return request<CommercialPlan>(`/api/admin/settings/plans/${planId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function listSubscriptions() {
  return request<TenantSubscriptionInfo[]>("/api/admin/settings/subscriptions");
}

export async function updateSubscription(tenantId: number, input: SubscriptionUpdateInput) {
  return request<TenantSubscriptionInfo & { plan_code: string }>(
    `/api/admin/settings/subscriptions/${tenantId}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
}

export async function getCostCenterOverview() {
  return request<CostCenterOverview>("/api/admin/cost-center/overview");
}

export async function getCostCenterTenants() {
  return request<CostCenterTenantRow[]>("/api/admin/cost-center/tenants");
}

export async function exportCostCenterCsv() {
  const res = await fetch(`${API_BASE}/api/admin/cost-center/export`, {
    credentials: "include",
  });
  if (!res.ok) throw await buildApiError(res, "成本中心导出失败");
  return res.text();
}

export async function getValueDashboard() {
  return request<ValueDashboardData>("/api/admin/cost-center/value-dashboard");
}

export async function listModelRoutingRules() {
  return request<ModelRoutingRule[]>("/api/admin/model-routing");
}

export async function upsertModelRoutingRule(input: ModelRoutingRuleInput) {
  return request<{ id: number }>("/api/admin/model-routing", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function listValuationRules() {
  return request<ValuationRule[]>("/api/admin/valuation-rules");
}

export async function upsertValuationRule(input: ValuationRuleInput) {
  return request<{ id: number }>("/api/admin/valuation-rules", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function listApprovalRequests() {
  return request<ApprovalRequestInfo[]>("/api/admin/approval-requests");
}

export async function createApprovalRequest(input: {
  type: string;
  reason: string;
  related_object_type?: string;
  related_object_id?: string;
  estimated_cost: number;
  metadata?: Record<string, unknown>;
}) {
  return request<ApprovalRequestInfo>("/api/admin/approval-requests", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function approveApprovalRequest(id: number, actualCost: number) {
  return request<ApprovalRequestInfo>(`/api/admin/approval-requests/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actual_cost: actualCost }),
  });
}

export async function rejectApprovalRequest(id: number, actualCost: number = 0) {
  return request<ApprovalRequestInfo>(`/api/admin/approval-requests/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actual_cost: actualCost }),
  });
}

// ---- Types ----

export interface PricingParameters {
  towing_cost: number;
  daily_parking: number;
  capital_rate: number;
  disposal_period: number;
  vehicle_condition?: "excellent" | "good" | "normal";
  buyout_strategy?: "direct" | "discount" | "ai_suggest";
  discount_rate?: number | null;
  advanced_condition_pricing?: boolean;
  manual_selected?: boolean;
  approval_mode?: boolean;
  approval_request_id?: number | null;
  strict_policy?: boolean;
  single_task_budget?: number | null;
}

export interface AssetPricingResult {
  row_number: number;
  car_description: string;
  buyout_price: number;
  che300_valuation: number | null;
  depreciation_rate: number | null;
  towing_cost: number;
  parking_cost: number;
  capital_cost: number;
  total_cost: number;
  expected_revenue: number;
  net_profit: number;
  profit_margin: number;
  risk_flags: string[];
}

export interface PackageSummary {
  total_assets: number;
  total_buyout_cost: number;
  total_expected_revenue: number;
  total_net_profit: number;
  overall_roi: number;
  recommended_max_discount: number;
  high_risk_count: number;
  risk_alerts: string[];
}

export interface PackageCalculationResult {
  package_id: number;
  summary: PackageSummary;
  assets: AssetPricingResult[];
}

export interface SandboxInput {
  car_description: string;
  entry_date: string;
  overdue_amount: number;
  che300_value: number;
  vehicle_type?: string;
  vehicle_age_years?: number;
  daily_parking?: number;
  recovery_cost?: number;
  annual_interest_rate?: number;
  expected_sale_days?: number;
  commission_rate?: number;
  litigation_lawyer_fee?: number;
  litigation_has_recovery_fee?: boolean;
  litigation_recovery_fee_rate?: number;
  special_lawyer_fee?: number;
  special_has_recovery_fee?: boolean;
  special_recovery_fee_rate?: number;
  restructure_monthly_payment?: number;
  restructure_months?: number;
  restructure_redefault_rate?: number;
}

export interface LegalCostDetail {
  court_fee: number;
  execution_fee: number;
  preservation_fee: number;
  lawyer_fee_fixed: number;
  lawyer_fee_recovery: number;
  total_legal_cost: number;
}

export interface AuctionRound {
  round_name: string;
  discount_rate: number;
  auction_price: number;
  success_probability: number;
}

export interface TimePoint {
  days: number;
  accumulated_parking: number;
  accumulated_interest: number;
  depreciated_value: number;
  depreciation_amount: number;
  total_holding_cost: number;
  total_shrinkage: number;
  net_position: number;
}

export interface LitigationScenario {
  label: string;
  duration_months: number;
  duration_days: number;
  legal_cost: LegalCostDetail;
  parking_cost: number;
  interest_cost: number;
  recovery_cost: number;
  auction_rounds: AuctionRound[];
  expected_auction_price: number;
  total_cost: number;
  net_recovery: number;
}

export interface SandboxResult {
  id: number;
  input: SandboxInput;
  path_a: {
    name: string;
    timepoints: TimePoint[];
    summary: string;
  };
  path_b: {
    name: string;
    legal_cost: LegalCostDetail;
    scenarios: LitigationScenario[];
    summary: string;
  };
  path_c: {
    name: string;
    expected_sale_days: number;
    sale_price: number;
    commission: number;
    parking_during_sale: number;
    recovery_cost: number;
    net_recovery: number;
    summary: string;
  };
  path_d: {
    name: string;
    duration_months: number;
    duration_days: number;
    legal_cost: LegalCostDetail;
    parking_cost: number;
    interest_cost: number;
    recovery_cost: number;
    auction_rounds: AuctionRound[];
    expected_auction_price: number;
    total_cost: number;
    net_recovery: number;
    summary: string;
  };
  path_e: {
    name: string;
    monthly_payment: number;
    total_months: number;
    total_expected_recovery: number;
    redefault_rate: number;
    risk_adjusted_recovery: number;
    holding_cost: number;
    net_recovery: number;
    summary: string;
  };
  recommendation: string;
  best_path: string;
}

// ============ 驾驶舱Types ============

export interface PortfolioOverviewData {
  snapshot_date: string;
  total_ead: number;
  total_asset_count: number;
  total_expected_loss: number;
  total_expected_loss_rate: number;
  cash_30d: number;
  cash_90d: number;
  cash_180d: number;
  recovered_rate: number;
  in_inventory_rate: number;
  avg_inventory_days: number;
  high_risk_segment_count: number;
  provision_impact: number;
  capital_release_score: number;
  monthly_judgment: string;
  top_risks: string[];
  top_actions: string[];
  resource_suggestions: string[];
  charts: {
    overdue_distribution: Array<{ bucket: string; ead: number }>;
    status_distribution: Array<{ status: string; ead: number }>;
    cashflow_trend: Array<{ period: string; amount: number }>;
  };
}

export interface SegmentationData {
  dimension: string;
  total_ead: number;
  total_loss: number;
  groups: Array<{
    dimension_value: string;
    asset_count: number;
    total_ead: number;
    expected_loss_amount: number;
    expected_loss_rate: number;
    cash_30d: number;
    cash_90d: number;
    cash_180d: number;
    sub_segments: Array<Record<string, unknown>>;
  }>;
}

export interface StrategyComparisonItem {
  strategy_type: string;
  strategy_name: string;
  success_probability: number;
  expected_recovery_gross: number;
  total_cost: number;
  net_recovery_pv: number;
  expected_loss_amount: number;
  expected_loss_rate: number;
  expected_recovery_days: number;
  capital_release_score: number;
  cost_breakdown: Record<string, number>;
  risk_notes: string[];
  not_recommended_reasons: string[];
}

export interface StrategyData {
  segment_index: number;
  segment_name: string;
  segment_ead: number;
  segment_count: number;
  strategies: StrategyComparisonItem[];
  recommended_strategy: string | null;
  total_segments: number;
  segment_list: Array<{ index: number; name: string }>;
}

export interface CashflowBucketItem {
  bucket_day: number;
  gross_cash_in: number;
  gross_cash_out: number;
  net_cash_flow: number;
}

export interface CashflowData {
  snapshot_date: string;
  total_ead: number;
  total_buckets: CashflowBucketItem[];
  by_strategy: Array<{
    strategy_type: string;
    strategy_name: string;
    buckets: CashflowBucketItem[];
    total_net_cash: number;
  }>;
  by_segment: Array<{
    segment_name: string;
    buckets: CashflowBucketItem[];
    total_net_cash: number;
  }>;
  total_long_tail: number;
  cash_return_rate: number;
}

export interface RoleRecommendation {
  role_level: string;
  recommendation_title: string;
  recommendation_text: string;
  expected_impact: Record<string, string>;
  feasibility_score: number;
  realism_score: number;
  priority: number;
  approval_needed: boolean;
}

export interface ExecutiveData {
  overview: PortfolioOverviewData;
  loss_contribution_by_segment: Array<{
    segment_name: string;
    loss_amount: number;
    loss_rate: number;
    contribution_pct: number;
    cash_30d: number;
  }>;
  resource_suggestions: string[];
  approval_items: string[];
  recommendations: RoleRecommendation[];
}

export interface ManagerData {
  recommendations: RoleRecommendation[];
  kpis: Array<{
    name: string;
    recommended_value: number;
    unit: string;
    historical_avg: number;
    achievable_value: number;
    risk_note: string;
  }>;
  weekly_rhythm: Array<{
    week: number;
    focus: string;
    actions: string[];
  }>;
}

export interface SupervisorData {
  recommendations: RoleRecommendation[];
  high_priority_pool: Array<{
    segment_name: string;
    status: string;
    next_action: string;
    urgency: string;
    loss_impact: number;
    cash_impact: number;
  }>;
}

export interface ActionCenterData {
  recommendations: RoleRecommendation[];
  auction_ready: Array<{
    segment_name: string;
    count: number;
    estimated_value: number;
    recommended_floor_price: number;
    risk_tags: string[];
  }>;
  recovery_tasks: Array<{
    segment_name: string;
    count: number;
    overdue_bucket: string;
    total_ead: number;
  }>;
}
