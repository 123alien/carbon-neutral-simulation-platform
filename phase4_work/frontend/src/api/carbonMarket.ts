import { http } from "./http";
import { silentConfig } from "./http";
import type {
  CarbonCostAssessment,
  CarbonMarketAssessmentCreate,
  CarbonMarketBatchComparison,
  CarbonMarketScenario,
  CarbonMarketStatistics,
} from "@/types";
export const carbonMarketApi = {
  scenario: (versionId: number) =>
    http.get<never, CarbonMarketScenario>(
      `/api/carbon-market/scenarios/${versionId}`,
      silentConfig,
    ),
  statistics: (params: { region: string; start?: string; end?: string }) =>
    http.get<never, CarbonMarketStatistics>("/api/carbon-market/statistics", {
      ...silentConfig,
      params,
    }),
  assessments: (params?: { scenario_version_id?: number; task_id?: number }) =>
    http.get<never, CarbonCostAssessment[]>("/api/carbon-market/assessments", {
      params,
    }),
  assessment: (id: number) =>
    http.get<never, CarbonCostAssessment>(
      `/api/carbon-market/assessments/${id}`,
    ),
  assess: (payload: CarbonMarketAssessmentCreate) =>
    http.post<never, CarbonCostAssessment>(
      "/api/carbon-market/assessments",
      payload,
      silentConfig,
    ),
  batchComparison: (id: number) =>
    http.get<never, CarbonMarketBatchComparison>(
      `/api/carbon-market/batches/${id}/comparison`,
    ),
};
