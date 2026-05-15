import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AssetPricingPage from "./page";
import {
  calculatePackage,
  getPackage,
  uploadExcel,
  type PackageCalculationResult,
} from "@/lib/api";
import { pollJob } from "@/lib/jobs";

vi.mock("@/lib/jobs", () => ({
  pollJob: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    uploadExcel: vi.fn(),
    calculatePackage: vi.fn(),
    getPackage: vi.fn(),
    createApprovalRequest: vi.fn(),
    listApprovalRequests: vi.fn(() => Promise.resolve([])),
  };
});

const mockUploadExcel = vi.mocked(uploadExcel);
const mockCalculatePackage = vi.mocked(calculatePackage);
const mockGetPackage = vi.mocked(getPackage);
const mockPollJob = vi.mocked(pollJob);

const packageResult: PackageCalculationResult = {
  package_id: 11,
  summary: {
    total_assets: 2,
    total_buyout_cost: 150000,
    total_expected_revenue: 150000,
    total_net_profit: -120000,
    overall_roi: 55.6,
    recommended_max_discount: 0.78,
    asset_package_type: "inventory",
    discount_basis: "车300车辆评估价",
    total_principal: 270000,
    total_vehicle_valuation: 190000,
    valuation_coverage_rate: 100,
    recommended_transfer_price_low: 136000,
    recommended_transfer_price_mid: 150000,
    recommended_transfer_price_high: 164000,
    recommended_discount_low: 0.71,
    recommended_discount_mid: 0.78,
    recommended_discount_high: 0.85,
    principal_recovery_rate_low: 0.5037,
    principal_recovery_rate_mid: 0.5556,
    principal_recovery_rate_high: 0.6074,
    valuation_realization_rate_low: 0.7158,
    valuation_realization_rate_mid: 0.7895,
    valuation_realization_rate_high: 0.8632,
    collateral_coverage_ratio: 0.7037,
    analysis_report: "一、资产包概览\n建议以中位价作为谈判底线。",
    pricing_methodology: "在库车资产包以车300车辆评估价为主锚。",
    high_risk_count: 0,
    risk_alerts: [],
    requested_strategy: "seller_transfer_analysis",
    discount_rate_used: null,
    strategy_breakdown: {
      inventory_valuation_discount: 2,
    },
  },
  assets: [
    {
      row_number: 2,
      car_description: "测试车辆-2",
      loan_principal: 120000,
      buyout_price: 78000,
      applied_strategy: "inventory_valuation_discount",
      che300_valuation: 100000,
      pricing_basis: "车300车辆评估价",
      pricing_basis_amount: 100000,
      recommended_transfer_price_low: 71000,
      recommended_transfer_price_mid: 78000,
      recommended_transfer_price_high: 85000,
      recommended_discount_low: 0.71,
      recommended_discount_mid: 0.78,
      recommended_discount_high: 0.85,
      principal_discount_low: 0.5917,
      principal_discount_mid: 0.65,
      principal_discount_high: 0.7083,
      valuation_discount_low: 0.71,
      valuation_discount_mid: 0.78,
      valuation_discount_high: 0.85,
      collateral_coverage_ratio: 0.8333,
      exposure_gap: 20000,
      depreciation_rate: null,
      towing_cost: 0,
      parking_cost: 0,
      capital_cost: 0,
      total_cost: 0,
      expected_revenue: 78000,
      net_profit: -42000,
      profit_margin: 65,
      risk_flags: ["基础字段完整-可进入买方询价"],
    },
  ],
};

async function uploadSamplePackage(user: ReturnType<typeof userEvent.setup>) {
  mockUploadExcel.mockResolvedValueOnce({
    package_id: 11,
    filename: "sample.xlsx",
    parse_result: {
      total_rows: 2,
      success_rows: 2,
      errors: [],
      column_mapping: {
        "车型": "car_description",
        "本金": "loan_principal",
      },
      unmapped_columns: ["买断价"],
      suggested_strategy: "seller_transfer_analysis",
      strategy_message: "已识别到本金/债权列。请先确认资产包是否为在库车。",
    },
  });

  render(<AssetPricingPage />);
  const fileInput = screen.getByLabelText("资产包Excel文件", { selector: "input" });
  const file = new File(["demo"], "sample.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  await user.upload(fileInput, file);
  await user.click(screen.getByRole("button", { name: "上传并解析" }));
  await screen.findByText("成功解析 2/2 行");
}

describe("AssetPricingPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("generates seller-side transfer analysis for the selected package type", async () => {
    const user = userEvent.setup();
    await uploadSamplePackage(user);

    mockCalculatePackage.mockResolvedValueOnce({ job_id: 99, status: "queued" });
    mockPollJob.mockResolvedValueOnce({
      id: 99,
      job_type: "calculate",
      status: "succeeded",
      payload_json: null,
      result_json: null,
      error_code: null,
      error_message: null,
      created_at: null,
      started_at: null,
      finished_at: null,
    });
    mockGetPackage.mockResolvedValueOnce({
      id: 11,
      name: "sample.xlsx",
      results: packageResult,
    });

    await user.click(screen.getByRole("button", { name: "生成资产包出让分析" }));

    await waitFor(() => {
      expect(mockCalculatePackage).toHaveBeenCalledWith(
        11,
        expect.objectContaining({
          asset_package_type: "inventory",
          vehicle_condition: "good",
        }),
      );
    });
    expect(await screen.findByText("资产包出让分析报告")).toBeInTheDocument();
    expect(screen.getByText(/建议以中位价作为谈判底线/)).toBeInTheDocument();
  });
});
