import { http } from "./http";
import type {
  AnnualSimulationRequest,
  AnnualSimulationResult,
  Enterprise,
  GridFactor,
  HourlySimulationRequest,
  HourlySimulationResult,
  LongTermPathRequest,
  LongTermPathRun,
  MarketPrice,
  QualitySummary,
  Scenario,
  SimulationBatch,
  SimulationBatchRequest,
  SimulationTask,
  StrengthenedPathRequest,
  WeatherSite,
} from "@/types";
export const simulationApi = {
  scenarios: (enterpriseId: number) =>
    http.get<never, Scenario[]>("/api/scenarios", {
      params: { enterprise_id: enterpriseId },
    }),
  enterprise: (id: number) =>
    http.get<never, Enterprise>(`/api/enterprises/${id}`),
  models: () =>
    http.get<never, { models: string[]; measure_types: string[] }>(
      "/api/simulation/hourly/models",
    ),
  runAnnual: (payload: AnnualSimulationRequest) =>
    http.post<never, AnnualSimulationResult>("/api/simulation/run", payload),
  getTask: (id: number) =>
    http.get<never, AnnualSimulationResult>(`/api/simulation/${id}`),
  runLongTerm: (payload: LongTermPathRequest) =>
    http.post<never, LongTermPathRun>("/api/simulation/long-term/run", payload),
  longTermRuns: (enterpriseId: number) =>
    http.get<never, LongTermPathRun[]>("/api/simulation/long-term/runs", {
      params: { enterprise_id: enterpriseId },
    }),
  getLongTerm: (id: number) =>
    http.get<never, LongTermPathRun>(`/api/simulation/long-term/${id}`),
  strengthenLongTerm: (id: number, payload: StrengthenedPathRequest) =>
    http.post<never, LongTermPathRun>(
      `/api/simulation/long-term/${id}/strengthen`,
      payload,
    ),
  batches: (enterpriseId?: number) =>
    http.get<never, SimulationBatch[]>("/api/simulation/batches", {
      params: { enterprise_id: enterpriseId },
    }),
  runBatch: (payload: SimulationBatchRequest) =>
    http.post<never, SimulationBatch>("/api/simulation/batches", payload),
  getBatch: (id: number) =>
    http.get<never, SimulationBatch>(`/api/simulation/batches/${id}`),
  runHourly: (payload: HourlySimulationRequest) =>
    http.post<never, HourlySimulationResult>(
      "/api/simulation/hourly/run",
      payload,
    ),
  getHourly: (id: number) =>
    http.get<
      never,
      { task: SimulationTask; results: HourlySimulationResult["results"] }
    >(`/api/simulation/hourly/${id}`),
  loadQuality: (
    enterpriseId: number,
    start: string,
    end: string,
    timezone: string,
  ) =>
    http.get<never, QualitySummary>("/api/loads/data-quality", {
      params: { enterprise_id: enterpriseId, start, end, timezone },
    }),
  weatherSites: (enterpriseId: number) =>
    http.get<never, WeatherSite[]>("/api/weather/sites", {
      params: { enterprise_id: enterpriseId },
    }),
  weatherQuality: (
    siteId: number,
    start: string,
    end: string,
    timezone: string,
  ) =>
    http.get<never, QualitySummary>("/api/weather/data-quality", {
      params: { site_id: siteId, start, end, timezone },
    }),
  prices: (enterpriseId: number, start: string, end: string) =>
    http.get<never, MarketPrice[]>("/api/market/prices", {
      params: { enterprise_id: enterpriseId, start, end },
    }),
  factors: (region: string, start: string, end: string) =>
    http.get<never, GridFactor[]>("/api/market/grid-factors", {
      params: { region, start, end },
    }),
};
