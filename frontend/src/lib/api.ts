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
export interface ParsedAssetInfo {
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
}

export interface AssetFieldOverride {
  car_description?: string;
  vin?: string;
  first_registration?: string;
  mileage?: number;
  gps_online?: boolean;
  insurance_lapsed?: boolean;
  ownership_transferred?: boolean;
  loan_principal?: number;
}

export async function uploadExcel(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<{
    package_id: number;
    filename: string;
    parse_result: {
      assets: ParsedAssetInfo[];
      errors: Array<{ row_number: number; field: string; message: string }>;
      total_rows: number;
      success_rows: number;
      column_mapping: Record<string, string>;
      unmapped_columns: string[];
      suggested_strategy: "seller_transfer_analysis";
      strategy_message: string;
    };
  }>("/api/asset-package/upload", { method: "POST", body: form });
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
  return request<{
    id: number;
    name: string;
    parameters: PricingParameters | null;
    results: PackageCalculationResult | null;
  }>(
    `/api/asset-package/${packageId}`
  );
}

// 下载资产包出让分析PDF
export async function downloadAssetPackageReportPdf(packageId: number): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/asset-package/${packageId}/report.pdf`, {
    credentials: "include",
  });
  if (!res.ok) {
    throw await buildApiError(res, "PDF下载失败");
  }
  return res.blob();
}

export async function analyzeBuyerOffer(
  packageId: number,
  input: { buyer_offer_price: number; buyer_offer_note?: string | null },
) {
  return request<BuyerOfferAnalysis>(
    `/api/asset-package/${packageId}/buyer-offer-analysis`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
}

export async function getTransferCompliance(packageId: number) {
  return request<TransferComplianceResult>(
    `/api/asset-package/${packageId}/compliance-checklist`,
  );
}

export async function updateTransferCompliance(
  packageId: number,
  checklist: TransferComplianceChecklist,
) {
  return request<TransferComplianceResult>(
    `/api/asset-package/${packageId}/compliance-checklist`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(checklist),
    },
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

export async function getCapacityPlan() {
  return request<PortfolioCapacityPlan>("/api/portfolio/capacity-plan");
}

export async function getCapacitySettings() {
  return request<PortfolioCapacitySettings>("/api/admin/settings/capacity");
}

export async function updateCapacitySettings(input: PortfolioCapacitySettings) {
  return request<PortfolioCapacitySettings>("/api/admin/settings/capacity", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function getAiCommandOverview() {
  return request<AiCommandOverview>("/api/ai-command-center/overview");
}

export async function runAiCommandAgent(input: AgentRunCreateInput) {
  return request<AgentRun>("/api/ai-command-center/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function listAiAgentRuns(limit: number = 20) {
  return request<AgentRun[]>(`/api/ai-command-center/runs?limit=${limit}`);
}

export async function listAiDecisionAuditLogs(limit: number = 20) {
  return request<DecisionAuditLog[]>(`/api/ai-command-center/decision-audit-logs?limit=${limit}`);
}

export async function getAiAgentRuleSettings(params?: { agent_type?: string; scenario?: string }) {
  const query = new URLSearchParams();
  if (params?.agent_type) query.set("agent_type", params.agent_type);
  if (params?.scenario) query.set("scenario", params.scenario);
  const qs = query.toString();
  return request<AgentRuleSettings>(`/api/ai-command-center/settings${qs ? `?${qs}` : ""}`);
}

export async function updateAiAgentRuleSettings(input: AgentRuleSettingsInput) {
  return request<AgentRuleSettings>("/api/ai-command-center/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function listAiAgentRuleProfiles() {
  return request<AgentRuleProfileSummary[]>("/api/ai-command-center/settings/profiles");
}

export async function listAiAgentRunReviews(limit: number = 20) {
  return request<AgentRunReview[]>(`/api/ai-command-center/run-reviews?limit=${limit}`);
}

export async function getAiAgentRunReviewInsights(limit: number = 100) {
  return request<AgentReviewInsight>(`/api/ai-command-center/run-reviews/insights?limit=${limit}`);
}

export async function createAiAgentRunReview(runId: number, input: AgentRunReviewInput) {
  return request<AgentRunReview>(`/api/ai-command-center/runs/${runId}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function listDisposalTasks(params?: { status?: string; task_type?: string }) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.task_type) query.set("task_type", params.task_type);
  const qs = query.toString();
  return request<DisposalTask[]>(`/api/tasks${qs ? `?${qs}` : ""}`);
}

export async function getDisposalTask(taskId: number) {
  return request<DisposalTask>(`/api/tasks/${taskId}`);
}

export async function listTaskAssignees() {
  return request<TaskAssignee[]>("/api/tasks/assignees");
}

export async function createDisposalTask(input: DisposalTaskCreateInput) {
  return request<DisposalTask>("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function assignDisposalTask(taskId: number, ownerUserId: number) {
  return request<DisposalTask>(`/api/tasks/${taskId}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ owner_user_id: ownerUserId }),
  });
}

export async function completeDisposalTask(taskId: number, input: DisposalTaskCompleteInput) {
  return request<DisposalTask>(`/api/tasks/${taskId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export async function uploadTaskEvidence(taskId: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<TaskEvidenceUpload>(`/api/tasks/${taskId}/evidence`, {
    method: "POST",
    body: form,
  });
}

export async function generateTasksFromPortfolio() {
  return request<DisposalTask[]>("/api/tasks/generate-from-portfolio", { method: "POST" });
}

export async function generateTaskFromSandbox(resultId: number) {
  return request<DisposalTask>(`/api/tasks/generate-from-sandbox/${resultId}`, { method: "POST" });
}

export async function listAuditLogs(params?: { action?: string }) {
  const query = new URLSearchParams();
  if (params?.action) query.set("action", params.action);
  const qs = query.toString();
  return request<AuditLogRow[]>(`/api/admin/audit-logs${qs ? `?${qs}` : ""}`);
}

export async function exportAuditLogsCsv(params?: { action?: string }): Promise<string> {
  const query = new URLSearchParams();
  if (params?.action) query.set("action", params.action);
  const res = await fetch(`${API_BASE}/api/admin/audit-logs/export${query.toString() ? `?${query}` : ""}`, {
    credentials: "include",
  });
  if (!res.ok) throw await buildApiError(res, "审计日志导出失败");
  return res.text();
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

export interface FeatureCatalogItem {
  key: string;
  label: string;
  category: string;
  description: string;
}

export interface PlanFeatureRow {
  plan_id: number;
  plan_code: string;
  plan_name: string;
  features: Record<string, boolean>;
}

export interface TenantFeatureRow {
  tenant_id: number;
  tenant_code: string | null;
  tenant_name: string | null;
  plan_code: string | null;
  plan_name: string | null;
  overrides: Record<string, boolean | null>;
  effective_features: Record<string, boolean>;
}

export interface FeatureFlagsSnapshot {
  catalog: FeatureCatalogItem[];
  plans: PlanFeatureRow[];
  tenants: TenantFeatureRow[];
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
  estimated_extra_recovery: number;
  avoided_loss_amount: number;
  accelerated_cash_in: number;
  manual_valuation_cost_saved: number;
  auction_price_improvement: number;
  bad_asset_identification_count: number;
  reports_generated: number;
  hours_saved: number;
  task_completion_rate: number;
  tenant_value_rows: Array<{
    tenant_id: number;
    tenant_code: string;
    tenant_name: string;
    task_count: number;
    completed_task_count: number;
    expected_recovery: number;
    actual_recovery: number;
    estimated_extra_recovery: number;
  }>;
  customer_summary: string;
  source_trace: Record<string, number>;
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

export async function getFeatureFlagsSnapshot() {
  return request<FeatureFlagsSnapshot>("/api/admin/feature-flags");
}

// Backward-compatible alias for older production pages that imported the singular name.
export const getFeatureFlagSnapshot = getFeatureFlagsSnapshot;

export async function updatePlanFeatureFlags(
  planCode: string,
  features: Record<string, boolean>,
) {
  return request<PlanFeatureRow>(`/api/admin/feature-flags/plans/${planCode}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ features }),
  });
}

export async function updateTenantFeatureFlags(
  tenantId: number,
  features: Record<string, boolean | null>,
) {
  return request<TenantFeatureRow>(`/api/admin/feature-flags/tenants/${tenantId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ features }),
  });
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
  asset_package_type?: "inventory" | "non_inventory";
  buyout_strategy?: "direct" | "discount" | "ai_suggest";
  discount_rate?: number | null;
  advanced_condition_pricing?: boolean;
  manual_selected?: boolean;
  approval_mode?: boolean;
  approval_request_id?: number | null;
  strict_policy?: boolean;
  single_task_budget?: number | null;
  asset_overrides?: Record<number, AssetFieldOverride>;
}

export interface AssetPricingResult {
  row_number: number;
  car_description: string;
  loan_principal: number | null;
  buyout_price: number;
  applied_strategy?: string;
  che300_valuation: number | null;
  pricing_basis: string;
  pricing_basis_amount: number;
  recommended_transfer_price_low: number;
  recommended_transfer_price_mid: number;
  recommended_transfer_price_high: number;
  recommended_discount_low: number;
  recommended_discount_mid: number;
  recommended_discount_high: number;
  principal_discount_low: number | null;
  principal_discount_mid: number | null;
  principal_discount_high: number | null;
  valuation_discount_low: number | null;
  valuation_discount_mid: number | null;
  valuation_discount_high: number | null;
  collateral_coverage_ratio: number | null;
  exposure_gap: number | null;
  depreciation_rate: number | null;
  towing_cost: number;
  parking_cost: number;
  capital_cost: number;
  total_cost: number;
  expected_revenue: number;
  net_profit: number;
  profit_margin: number;
  risk_flags: string[];
  valuation_confidence_score?: number;
  valuation_confidence_level?: "high" | "medium" | "low" | "very_low" | "mock" | "unknown";
  valuation_source?: string;
  valuation_warnings?: string[];
  valuation_anomaly_tags?: string[];
  energy_type?: "fuel" | "bev" | "phev" | "erev" | "hybrid" | "unknown";
  market_liquidity_score?: number;
  market_liquidity_level?: "high" | "medium" | "low" | "very_low";
  market_liquidity_adjustment?: number;
  expected_sale_days_adjusted?: number;
  liquidity_risk_tags?: string[];
  new_energy_risk_tags?: string[];
  new_energy_adjustment?: number;
}

export interface BuyerOfferAnalysis {
  buyer_offer_price: number;
  buyer_offer_note: string | null;
  buyer_offer_discount: number | null;
  buyer_offer_gap: number;
  buyer_offer_gap_rate: number | null;
  buyer_offer_assessment: string;
  negotiation_suggestions: string[];
}

export interface TransferComplianceChecklist {
  asset_scope_confirmed?: boolean;
  internal_approval_completed?: boolean;
  asset_authenticity_verified?: boolean;
  transfer_restriction_checked?: boolean;
  pricing_basis_archived?: boolean;
  inquiry_process_recorded?: boolean;
  debtor_notification_arranged?: boolean;
  no_hidden_repurchase_commitment?: boolean;
  archive_completed?: boolean;
  watermark_export_completed?: boolean;
}

export interface TransferComplianceResult {
  compliance_score: number;
  compliance_level: string;
  checklist: TransferComplianceChecklist;
  missing_items: string[];
  risk_warnings: string[];
  archive_requirements: string[];
  summary: string;
}

export interface PackageSummary {
  total_assets: number;
  total_buyout_cost: number;
  total_expected_revenue: number;
  total_net_profit: number;
  overall_roi: number;
  recommended_max_discount: number;
  asset_package_type: "inventory" | "non_inventory";
  discount_basis: string;
  total_principal: number;
  total_vehicle_valuation: number;
  valuation_coverage_rate: number;
  recommended_transfer_price_low: number;
  recommended_transfer_price_mid: number;
  recommended_transfer_price_high: number;
  recommended_discount_low: number;
  recommended_discount_mid: number;
  recommended_discount_high: number;
  principal_recovery_rate_low: number | null;
  principal_recovery_rate_mid: number | null;
  principal_recovery_rate_high: number | null;
  valuation_realization_rate_low: number | null;
  valuation_realization_rate_mid: number | null;
  valuation_realization_rate_high: number | null;
  collateral_coverage_ratio: number | null;
  analysis_report: string;
  pricing_methodology: string;
  high_risk_count: number;
  risk_alerts: string[];
  requested_strategy?: string;
  discount_rate_used?: number | null;
  strategy_breakdown?: Record<string, number>;
  tradeability_score?: number;
  tradeability_level?: "A" | "B" | "C" | "D" | "E";
  tradeability_summary?: string;
  tradeability_recommendations?: string[];
  tradeability_breakdown?: Record<string, number>;
  buyer_offer_analysis?: BuyerOfferAnalysis | null;
  compliance_checklist?: TransferComplianceResult | null;
  avg_market_liquidity_score?: number | null;
  low_liquidity_count?: number;
  new_energy_asset_count?: number;
  market_liquidity_summary?: string;
}

export interface PackageCalculationResult {
  package_id: number;
  summary: PackageSummary;
  assets: AssetPricingResult[];
}

export interface SandboxInput {
  car_description: string;
  entry_date: string;
  overdue_bucket?: string;
  overdue_amount: number;
  che300_value: number;
  vehicle_type?: string;
  vehicle_age_years?: number;
  energy_type?: "fuel" | "bev" | "phev" | "erev" | "hybrid" | "unknown";
  battery_health_score?: number | null;
  battery_warranty_valid?: boolean | null;
  operating_vehicle?: boolean | null;
  ride_hailing_vehicle?: boolean | null;
  battery_replacement_history?: boolean | null;
  range_km?: number | null;
  daily_parking?: number;
  recovery_cost?: number;
  annual_interest_rate?: number;
  vehicle_recovered?: boolean;
  vehicle_in_inventory?: boolean;
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
  legal_materials?: LegalMaterialStatus;
  strategy_preference?: StrategyPreference;
}

export type StrategyPreference =
  | "maximize_recovery"
  | "accelerate_cashflow"
  | "reduce_legal_risk"
  | "reduce_execution_complexity";

export interface LegalMaterialStatus {
  loan_contract?: boolean;
  mortgage_contract?: boolean;
  mortgage_registration?: boolean;
  overdue_statement?: boolean;
  repayment_records?: boolean;
  debtor_identity?: boolean;
  collection_records?: boolean;
  vehicle_location_records?: boolean;
  inventory_certificate?: boolean;
  vehicle_photos?: boolean;
  valuation_report?: boolean;
  debt_balance_sheet?: boolean;
  guarantor_info?: boolean;
  title_check?: boolean;
  jurisdiction_clause?: boolean;
  debt_matured?: boolean;
  no_substantive_dispute?: boolean;
  no_title_abnormality?: boolean;
}

export interface LegalPathAssessment {
  path: "litigation" | "special_procedure";
  score: number;
  level: string;
  risk_tags: string[];
  material_gaps: string[];
  recommendation: string;
}

export interface PathDecisionScore {
  path: "A" | "B" | "C" | "D" | "E";
  score: number;
  net_recovery_score: number;
  time_score: number;
  legal_feasibility_score: number;
  execution_difficulty_score: number;
  cashflow_urgency_score: number;
  available: boolean;
  reason: string;
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
    legal_assessment?: LegalPathAssessment | null;
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
    market_liquidity_score?: number;
    market_liquidity_level?: "high" | "medium" | "low" | "very_low";
    market_liquidity_adjustment?: number;
    liquidity_risk_tags?: string[];
    new_energy_risk_tags?: string[];
    available?: boolean;
    unavailable_reason?: string;
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
    available?: boolean;
    unavailable_reason?: string;
    legal_assessment?: LegalPathAssessment | null;
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
  path_scores?: PathDecisionScore[];
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
  /**
   * @deprecated 2026-04-22 起系统不再做路径推荐，后端固定返回 null。
   *             保留字段仅为兼容旧前端，不要在新代码中读取。
   */
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

export interface PortfolioCapacitySettings {
  monthly_towing_capacity: number;
  monthly_litigation_capacity: number;
  monthly_auction_capacity: number;
  monthly_collection_capacity: number;
  inventory_yard_capacity: number;
  monthly_disposal_budget: number;
  legal_team_capacity: number;
  external_vendor_capacity: number;
}

export interface CapacityPlanItem {
  segment_name: string;
  strategy_type: string;
  strategy_name: string;
  task_type: string;
  asset_count: number;
  selected_count: number;
  deferred_count: number;
  expected_net_recovery: number;
  expected_incremental_recovery: number;
  required_cost: number;
  cash_return_speed: number;
  execution_feasibility: number;
  resource_needs: Record<string, number>;
  status: string;
  reason: string;
}

export interface PortfolioCapacityPlan {
  settings: PortfolioCapacitySettings;
  data_source?: string;
  snapshot_id?: number | null;
  snapshot_date?: string | null;
  segment_count?: number;
  asset_count?: number;
  generated_at?: string;
  empty_reason?: string | null;
  current_month_execution_plan: CapacityPlanItem[];
  next_month_deferred_pool: CapacityPlanItem[];
  paused_pool: CapacityPlanItem[];
  capacity_bottlenecks: string[];
  budget_gap: number;
  incremental_recovery_if_capacity_added: number;
  resource_usage: Record<string, number>;
  remaining_capacity: Record<string, number>;
  total_selected_assets: number;
  total_expected_net_recovery: number;
  total_expected_incremental_recovery: number;
  summary: string;
}

export type AiAgentType =
  | "asset_package_diagnosis_agent"
  | "valuation_analysis_agent"
  | "pricing_strategy_agent"
  | "buyer_offer_analysis_agent"
  | "operation_planning_agent"
  | "task_generation_agent"
  | "report_generation_agent"
  | "cost_control_agent";

export interface AgentEvidence {
  source: string;
  label: string;
  value: unknown;
  evidence_source?: string | null;
  related_object_type?: string | null;
  related_object_id?: string | null;
  calculation_basis?: string | null;
  data_quality_notes?: string | null;
}

export interface AgentOutput {
  summary: string;
  key_findings: string[];
  recommended_actions: string[];
  risk_warnings: string[];
  confidence_score: number;
  evidence: AgentEvidence[];
  requires_human_review: boolean;
  agent_status: string;
}

export interface AgentRunCreateInput {
  question?: string;
  agent_type?: AiAgentType;
  asset_package_id?: number;
  buyer_offer_price?: number;
  buyer_offer_note?: string;
  expected_vin_calls?: number;
  expected_condition_pricing_calls?: number;
  expected_ai_reports?: number;
  single_task_budget?: number;
  report_type?: string;
  rule_scenario?: string;
}

export interface AgentRun {
  id: number;
  tenant_id: number;
  agent_type: string;
  status: string;
  created_by: number | null;
  started_at: string;
  finished_at: string | null;
  requires_human_review: boolean;
  input: Record<string, unknown>;
  output: AgentOutput;
}

export interface AgentTask {
  id: number;
  agent_run_id: number | null;
  title: string;
  task_type: string;
  priority: string;
  status: string;
  requires_human_review: boolean;
  created_at: string;
  payload: Record<string, unknown>;
}

export interface AgentRecommendation {
  id: number;
  agent_run_id: number | null;
  recommendation_type: string;
  title: string;
  summary: string;
  confidence_score: number;
  requires_human_review: boolean;
  created_at: string;
}

export interface AgentWorkbenchItem {
  agent_type: AiAgentType;
  name: string;
  stage: string;
  status: string;
  min_role: string;
}

export interface AiCommandOverview {
  today_overview: {
    asset_package_count?: number;
    pending_work_orders?: number;
    pending_approval_count?: number;
    agent_runs_today?: number;
    [key: string]: unknown;
  };
  ai_today_judgment: AgentOutput;
  agent_workbench: AgentWorkbenchItem[];
  pending_tasks: AgentTask[];
  pending_approvals: AgentRecommendation[];
  recent_runs: AgentRun[];
  suggested_prompts: string[];
  role_scope: string;
}

export interface DecisionAuditLog {
  id: number;
  agent_run_id: number | null;
  decision_type: string;
  action: string;
  actor_user_id: number | null;
  requires_human_review: boolean;
  created_at: string;
  after: Record<string, unknown>;
}

export interface AgentRuleSettingsInput {
  agent_type?: string;
  scenario?: string;
  is_active?: boolean;
  operation_high_priority_limit: number;
  operation_data_gap_min_count: number;
  task_max_drafts: number;
  task_urgent_deadline_days: number;
  task_normal_deadline_days: number;
  cost_budget_warning_percent: number;
  cost_condition_call_approval_threshold: number;
  cost_ai_report_merge_threshold: number;
  report_confidence_floor: number;
  report_max_sections: number;
}

export interface AgentRuleSettings extends AgentRuleSettingsInput {
  tenant_id: number;
  agent_type: string;
  scenario: string;
  version: number;
  is_active: boolean;
  updated_by: number | null;
  updated_at: string | null;
}

export interface AgentRuleProfileSummary {
  tenant_id: number;
  agent_type: string;
  scenario: string;
  version: number;
  is_active: boolean;
  updated_by: number | null;
  updated_at: string | null;
}

export interface AgentRunReviewInput {
  outcome: "accepted" | "rejected" | "partial" | "needs_revision";
  usefulness_score: number;
  accuracy_score: number;
  accepted_actions_count: number;
  rejected_actions_count: number;
  follow_up_required: boolean;
  feedback?: string | null;
}

export interface AgentRunReview extends AgentRunReviewInput {
  id: number;
  tenant_id: number;
  agent_run_id: number;
  reviewer_user_id: number | null;
  feedback: string | null;
  created_at: string;
}

export interface AgentReviewInsight {
  tenant_id: number;
  review_count: number;
  average_usefulness_score: number;
  average_accuracy_score: number;
  accepted_actions_count: number;
  rejected_actions_count: number;
  follow_up_required_count: number;
  acceptance_rate: number;
  recommendations: string[];
  requires_human_review: boolean;
}

export interface DisposalTask {
  id: number;
  tenant_id: number;
  task_type: string;
  status: string;
  priority: string;
  title: string;
  target_description: string | null;
  source_type: string | null;
  source_id: string | null;
  owner_user_id: number | null;
  owner_user_email: string | null;
  owner_display_name: string | null;
  expected_recovery: number | null;
  expected_cost: number | null;
  deadline: string | null;
  evidence_files: string[];
  result_note: string | null;
  actual_recovery: number | null;
  variance_reason: string | null;
  completed_at?: string | null;
  payload: Record<string, unknown>;
  result: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DisposalTaskCreateInput {
  task_type: string;
  title: string;
  priority?: "high" | "medium" | "low" | "normal";
  target_description?: string | null;
  source_type?: string | null;
  source_id?: string | null;
  owner_user_id?: number | null;
  expected_recovery?: number | null;
  expected_cost?: number | null;
  deadline?: string | null;
  evidence_files?: string[];
}

export interface DisposalTaskCompleteInput {
  actual_recovery?: number | null;
  result_note?: string | null;
  variance_reason?: string | null;
  evidence_files?: string[];
}

export interface TaskAssignee {
  id: number;
  email: string;
  display_name: string | null;
  role: string;
}

export interface TaskEvidenceUpload {
  storage_key: string;
  filename: string;
  content_type: string;
  size: number;
}

export interface AuditLogRow {
  id: number;
  tenant_id: number | null;
  user_id: number | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  request_id: string | null;
  ip: string | null;
  user_agent: string | null;
  status: string;
  before_json: string | null;
  after_json: string | null;
  created_at: string | null;
}
