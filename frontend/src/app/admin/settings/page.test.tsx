import { render, screen } from "@testing-library/react";

import AdminSettingsPage from "./page";
import {
  listCommercialPlans,
  listSubscriptions,
} from "@/lib/api";
import { useSession } from "@/components/auth/session-provider";


vi.mock("@/components/admin/admin-access", () => ({
  AdminAccess: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/auth/session-provider", () => ({
  useSession: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    listCommercialPlans: vi.fn(),
    listSubscriptions: vi.fn(),
    createCommercialPlan: vi.fn(),
    updateSubscription: vi.fn(),
  };
});


const mockUseSession = vi.mocked(useSession);
const mockListCommercialPlans = vi.mocked(listCommercialPlans);
const mockListSubscriptions = vi.mocked(listSubscriptions);


describe("AdminSettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListCommercialPlans.mockResolvedValue([
      {
        id: 1,
        code: "standard",
        name: "Standard",
        billing_cycle_supported: "monthly,yearly",
        monthly_price: 1999,
        yearly_price: 19999,
        setup_fee: 0,
        private_deploy_fee: 0,
        seat_limit: 5,
        included_vin_calls: 100,
        included_condition_pricing_points: 5,
        included_ai_reports: 50,
        included_asset_packages: 20,
        included_sandbox_runs: 40,
        overage_vin_unit_price: 2,
        overage_condition_pricing_unit_price: 40,
        feature_flags: {},
        is_active: true,
      },
    ]);
    mockListSubscriptions.mockResolvedValue([
      {
        id: 1,
        tenant_id: 1,
        tenant_code: "default",
        tenant_name: "DEFAULT",
        plan_code: "standard",
        plan_name: "Standard",
        status: "active",
        monthly_budget_limit: 5000,
        alert_threshold_percent: 80,
      },
    ]);
  });

  it("shows plans but hides plan creation form for manager role", async () => {
    mockUseSession.mockReturnValue({
      user: { id: 1, role: "manager", email: "manager@example.com" },
      loading: false,
      refresh: vi.fn(),
      logout: vi.fn(),
      login: vi.fn(),
    });

    render(<AdminSettingsPage />);

    expect(await screen.findAllByText("Standard")).toHaveLength(2);
    expect(screen.getByText("租户订阅")).toBeInTheDocument();
    expect(screen.queryByText("新增套餐")).not.toBeInTheDocument();
  });
});
