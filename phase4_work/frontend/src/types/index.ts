export type Id = number;
export interface ApiError {
  message: string;
  status?: number;
  code?: string;
  details?: unknown;
}
export interface HealthStatus {
  status: string;
  version: string;
}
export interface Enterprise {
  id: Id;
  name: string;
  region?: string | null;
  industry?: string | null;
  building_area?: number | null;
  population?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  base_year: number;
  created_at?: string;
  updated_at?: string;
}
export interface Site {
  id: Id;
  enterprise_id: Id;
  organization_node_id?: Id | null;
  code: string;
  name: string;
  site_type:
    | "PARK"
    | "CAMPUS"
    | "PUBLIC_INSTITUTION"
    | "ENTERPRISE"
    | "STREET"
    | "OTHER";
  address?: string | null;
  area_m2?: number | null;
  population?: number | null;
  timezone: string;
  status: string;
  metadata_json: Record<string, unknown>;
  longitude?: number | null;
  latitude?: number | null;
  position_json?: Record<string, unknown> | null;
  geometry_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}
export interface Building {
  id: Id;
  site_id: Id;
  organization_node_id?: Id | null;
  code: string;
  name: string;
  building_type: string;
  area_m2?: number | null;
  floor_count?: number | null;
  population?: number | null;
  status: string;
  metadata_json: Record<string, unknown>;
  longitude?: number | null;
  latitude?: number | null;
  position_json?: Record<string, unknown> | null;
  geometry_json?: Record<string, unknown> | null;
}
export interface Device {
  id: Id;
  enterprise_id: Id;
  data_source_id?: Id | null;
  external_id: string;
  name: string;
  device_type: string;
  status: string;
  metadata_json: Record<string, unknown>;
  longitude?: number | null;
  latitude?: number | null;
  position_json?: Record<string, unknown> | null;
  geometry_json?: Record<string, unknown> | null;
}
export type SpatialLayerMode = "CARBON" | "ENERGY" | "DEVICE";
export interface SpatialCoordinate {
  x: number;
  y: number;
  z: number;
  source: "LOCAL" | "GEOGRAPHIC";
}
export interface SpatialSceneObject {
  id: number;
  kind: "BUILDING" | "DEVICE";
  name: string;
  type: string;
  coordinate: SpatialCoordinate;
  source: Building | Device;
  quality: "OK" | "NO_DATA";
}
export interface SpatialValidation {
  objects: SpatialSceneObject[];
  invalidCount: number;
}

/** 仅用于未来轨迹图层空间对齐；不代表跨镜系统最终接口。 */
export interface ReservedTrajectorySpatialReference {
  campus_id: string
  building_id: string | null
  floor_id: string | null
  area_id: string | null
  timestamp: string
  camera_id: string | null
}
export type FileDataNature = "MEASURED" | "SIMULATED" | "HISTORICAL";
export interface DataSource {
  id: Id;
  enterprise_id: Id;
  site_id?: Id | null;
  building_id?: Id | null;
  device_id?: Id | null;
  metering_point_id?: Id | null;
  data_nature?: FileDataNature | null;
  name: string;
  source_type: string;
  config_json?: Record<string, unknown>;
  status: string;
  has_credentials?: boolean;
  collection_mode: string;
  schedule_enabled: boolean;
  interval_minutes: number | null;
  last_sync_at?: string | null;
}
export interface DataSourceCreate {
  enterprise_id: number;
  site_id?: number | null;
  building_id?: number | null;
  device_id?: number | null;
  metering_point_id?: number | null;
  data_nature?: FileDataNature | null;
  name: string;
  source_type: "FILE" | "REST_API" | "MQTT" | "THIRD_PARTY" | "MANUAL";
  config_json: Record<string, unknown>;
  credentials?: Record<string, string> | null;
  status: string;
}
export interface DataSourceCapability {
  source_type: string;
  acquisition_mode: string;
  connection_test: boolean;
  manual_sync: boolean;
  scheduled_sync: boolean;
  realtime_listener: boolean;
  automatic_reconnect: boolean;
  field_mapping: boolean;
  validation_pipeline: string[];
  runtime_status: string;
  limitation: string | null;
}
export interface ValidationLog {
  id: number;
  data_source_id: number;
  device_external_id: string | null;
  timestamp: string | null;
  level: "ERROR" | "WARNING";
  validation_stage: "L1_SCHEMA" | "L2_SEMANTIC" | "L3_TEMPORAL";
  code: string;
  message: string;
  raw_json: Record<string, unknown> | null;
  created_at: string;
  disposition: string;
}
export interface AcquisitionOverview {
  source_count: number;
  normal_source_count: number;
  abnormal_source_count: number;
  never_run_count?: number;
  by_type: Record<string, number>;
  received_last_24h: number | null;
  last_success_sync_at: string | null;
  last_failure_at: string | null;
  validation: Record<
    string,
    { rejected: number; warnings?: number; passed: number | null }
  >;
  quarantined: number;
  quality_rate: number | null;
  latest_data_at: string;
  automatic_acquisition_running: boolean;
}
export interface DataSourceDetail {
  source: DataSource;
  protocol: string;
  capability: DataSourceCapability;
  security: {
    transport: string;
    secure_transport_enabled: boolean | null;
    tls_verification: boolean | null;
    authentication: string;
    credentials_configured: boolean;
    ca_configured: boolean | null;
    client_certificate_configured: boolean | null;
  };
  binding: {
    device_count: number;
    metering_point_count: number;
    devices: Array<{
      id: number;
      external_id: string;
      name: string;
      device_type: string;
      status: string;
    }>;
    metering_points: Array<{
      id: number;
      code: string;
      name: string;
      metric_type: string;
      energy_type: string;
      unit: string;
      device_id: number | null;
    }>;
  };
  status: {
    last_received_at: string;
    received_last_24h: number;
    cumulative_accepted: number;
    last_error: ValidationLog | null;
  };
  mapping: Record<string, string>;
  validation: DataQuality;
  validation_logs: ValidationLog[];
  latest_records: Array<{
    id: number;
    device_id: number;
    timestamp: string;
    metric_name: string;
    value: number;
    unit: string;
    quality: string;
  }>;
}
export interface DataSourceRuntime {
  data_source_id: number;
  source_type: string;
  collection_mode: string;
  schedule_enabled: boolean;
  interval_minutes: number | null;
  runtime_status:
    "STOPPED" | "STARTING" | "RUNNING" | "RECONNECTING" | "DEGRADED" | "ERROR";
  connected: boolean;
  subscribed: boolean;
  last_started_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  next_run_at: string | null;
  last_connected_at: string | null;
  last_disconnected_at: string | null;
  last_message_at: string | null;
  last_received_count: number;
  last_persisted_count: number;
  last_rejected_count: number;
  received_count: number;
  persisted_count: number;
  rejected_count: number;
  dropped_count: number;
  reconnect_count: number;
  consecutive_failures: number;
  current_topic: string | null;
  last_error: string | null;
  incremental_mode: "NONE" | "TIME_WINDOW" | "CURSOR";
  current_window_start: string | null;
  current_window_end: string | null;
  last_success_watermark: string | null;
  requested_pages: number;
  successful_pages: number;
  failed_page: number | null;
  pages_fetched: number;
  records_fetched: number;
  duplicates_skipped: number;
}
export interface ImportErrorRow {
  row: number;
  field?: string | null;
  code?: string;
  message: string;
  value?: unknown;
}
export interface ImportPreview {
  filename?: string;
  columns?: string[];
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows?: number;
  existing_rows?: number;
  interval_minutes?: number | null;
  missing_intervals?: number;
  missing_points?: number;
  can_confirm: boolean;
  preview: Record<string, unknown>[];
  errors: ImportErrorRow[];
}
export interface ImportConfirm {
  inserted_rows: number;
  enterprise_id?: number;
  site_id?: number;
  interval_minutes?: number;
  source?: string | null;
}
export interface GreenPowerContract {
  id: number;
  enterprise_id: number;
  name: string;
  start_at: string;
  end_at: string;
  purchase_kwh?: number | null;
  purchase_share?: number | null;
  emission_factor_kg_per_kwh: number;
  premium_per_kwh: number;
  status: string;
  source?: string | null;
}
export interface EnergySystem {
  id: Id;
  site_id: Id;
  building_id?: Id | null;
  code: string;
  name: string;
  system_type: string;
  status: string;
  metadata_json: Record<string, unknown>;
}
export interface MeteringPoint {
  id: Id;
  site_id: Id;
  building_id?: Id | null;
  energy_system_id?: Id | null;
  device_id?: Id | null;
  data_source_id?: Id | null;
  code: string;
  name: string;
  metric_type: string;
  energy_type: string;
  unit: string;
  status: string;
}
export interface CarbonAccounting {
  id: Id;
  enterprise_id: Id;
  name: string;
  period_start: string;
  period_end: string;
  status: string;
  summary_json: Record<string, unknown>;
}
export interface OrganizationNode {
  id: Id;
  enterprise_id: Id;
  parent_id?: Id | null;
  name: string;
  level: "ENTERPRISE" | "BUILDING_PARK" | "REGION" | string;
  code?: string | null;
  metadata_json: Record<string, unknown>;
}
export interface CarbonAccountingRun {
  id: Id;
  enterprise_id: Id;
  name: string;
  period_start: string;
  period_end: string;
  status: string;
  scopes_json: string[];
  summary_json: {
    activity_count?: number;
    total_emission_t?: number;
    scope_counts?: Record<string, number>;
    dynamic_factor_points_available?: number;
  };
  created_at: string;
}
export interface CarbonAccountingResult {
  id: Id;
  run_id: Id;
  enterprise_id: Id;
  organization_node_id?: Id | null;
  device_id?: Id | null;
  timestamp: string;
  energy_type: string;
  scope: string;
  activity_value: number;
  activity_unit: string;
  original_activity_value: number;
  original_activity_unit: string;
  emission_factor: number;
  factor_unit: string;
  factor_source?: string | null;
  factor_version: string;
  formula: string;
  standard_basis: string;
  emission_t: number;
  activity_source?: string | null;
}
export interface CarbonStatisticsItem {
  bucket_start: string;
  dimension_key: string;
  emission_t: number;
  record_count: number;
}
export interface CarbonStatistics {
  run_id: Id;
  granularity: "day" | "month" | "year";
  dimension: string;
  timezone: string;
  total_emission_t: number;
  items: CarbonStatisticsItem[];
}
export type EmissionFactorTrace = Pick<
  CarbonAccountingResult,
  | "id"
  | "energy_type"
  | "scope"
  | "original_activity_value"
  | "original_activity_unit"
  | "activity_value"
  | "activity_unit"
  | "emission_factor"
  | "factor_unit"
  | "factor_source"
  | "factor_version"
  | "formula"
  | "standard_basis"
>;
export interface SimulationTask {
  id: Id;
  scenario_id: Id;
  scenario_version_id?: Id | null;
  status: string;
  parameter_snapshot_json: Record<string, unknown>;
  summary_json?: Record<string, unknown> | null;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
}
export interface ScenarioMeasure {
  id?: Id;
  scenario_id?: Id;
  measure_type: MeasureType;
  start_year: number;
  end_year?: number | null;
  parameters_json: Record<string, unknown>;
}
export interface Scenario {
  id: Id;
  enterprise_id: Id;
  name: string;
  description?: string | null;
  base_year: number;
  start_year: number;
  end_year: number;
  scenario_type: string;
  current_version_id?: Id | null;
  status: string;
  measures?: ScenarioMeasure[];
  created_at: string;
}
export interface ScenarioVersionSnapshot {
  enterprise_id?: number;
  name?: string;
  description?: string | null;
  base_year?: number;
  start_year?: number;
  end_year?: number;
  target_peak_year?: number | null;
  target_neutral_year?: number | null;
  carbon_quota_t?: number | null;
  energy_target_kwh?: number | null;
  budget?: number | null;
  baseline_growth_json?: Record<string, unknown>;
  status?: string;
  scenario_type?: string;
  measures?: ScenarioMeasure[];
  electricity_price_per_kwh?: number;
  feed_in_tariff_per_kwh?: number;
  emission_factor?: Record<string, unknown>;
  green_power?: Record<string, unknown>;
  carbon_market?: Record<string, unknown>;
  risk_parameters?: Record<string, unknown>;
  [key: string]: unknown;
}
export interface ScenarioVersion {
  id: Id;
  scenario_id: Id;
  version_number: number;
  scenario_type: string;
  parameter_snapshot_json: ScenarioVersionSnapshot;
  carbon_market_snapshot_json?: Record<string, unknown> | null;
  risk_parameter_snapshot_json?: Record<string, unknown> | null;
  source_recommendation_id?: number | null;
  created_at: string;
}
export interface Recommendation {
  id: Id;
  profile: string;
  rank: number;
  score: number;
  measures_json: Record<string, unknown>[];
  reasons_json: string[];
  metrics_json: Record<string, unknown>;
}
export type RecommendationProfile = "ECONOMIC" | "REDUCTION" | "BALANCED";
export interface RecommendationWeights {
  reduction: number;
  investment: number;
  payback: number;
  applicability: number;
  target: number;
}
export interface RecommendationRequest {
  enterprise_id: number;
  simulation_year: number;
  target_peak_year?: number | null;
  target_neutral_year?: number | null;
  carbon_quota_t?: number | null;
  energy_target_kwh?: number | null;
  budget: number;
  top_n: number;
  weights: Partial<
    Record<RecommendationProfile, Partial<RecommendationWeights>>
  >;
  candidate_parameters: Record<
    string,
    { parameters?: Record<string, unknown>; capex?: number; disabled?: boolean }
  >;
}
export interface RecommendationMeasure {
  type: MeasureType;
  parameters: Record<string, unknown>;
  investment: number;
}
export interface RecommendationScore {
  estimated_reduction_t?: number;
  investment?: number;
  payback_years?: number | null;
  target_satisfaction?: number;
  technical_applicability?: number;
  grid_power_kwh?: number;
  carbon_emission_t?: number;
  score_dimensions?: RecommendationWeights;
}
export interface RecommendationValidationSummary {
  engine?: string;
  hours?: number;
  max_energy_balance_error_kwh?: number;
  baseline_carbon_emission_t?: number;
  validated?: boolean;
}
export interface RecommendationPath {
  id: number;
  profile: RecommendationProfile;
  rank: number;
  score: number;
  measures_json: RecommendationMeasure[];
  reasons_json: string[];
  metrics_json: RecommendationScore;
  validation_summary_json: RecommendationValidationSummary;
}
export interface RecommendationRun {
  id: number;
  enterprise_id: number;
  simulation_year: number;
  input_snapshot_json: RecommendationRequest;
  baseline_summary_json: Record<string, number>;
  created_at: string;
  recommendations: RecommendationPath[];
}
export interface RecommendationConversionRequest {
  name: string;
  description?: string;
  base_year: number;
  start_year: number;
  end_year: number;
  target_peak_year?: number | null;
  target_neutral_year?: number | null;
}
export interface RecommendationConversionResult extends Scenario {}
export interface LoadStatistics {
  total_electricity_kwh: number;
  peak_load_kw?: number | null;
  average_load_kw?: number | null;
  minimum_load_kw?: number | null;
  observed_points: number;
  expected_points: number;
  missing_points: number;
  completeness_rate: number;
  quality: string;
}
export interface WeatherStatisticsSummary {
  average_temperature_c?: number | null;
  average_humidity_pct?: number | null;
  peak_ghi_w_m2?: number | null;
  total_ghi_wh_m2: number;
  observed_points: number;
  expected_points: number;
  missing_points: number;
  completeness_rate: number;
  quality: string;
}
export interface WeatherHourlyPoint {
  wind_speed_m_s?: number | null;
  ghi_w_m2: number;
  timestamp: string;
}
export interface ScenarioComparisonMetric {
  cumulative_carbon_emission_t?: number;
  cumulative_carbon_reduction_t?: number;
  reduction_rate?: number;
  total_grid_power_kwh?: number;
  renewable_generation_kwh?: number;
  renewable_self_consumption_rate?: number;
  storage_charge_kwh?: number;
  storage_discharge_kwh?: number;
  total_electricity_cost?: number;
  investment?: number;
  payback_years?: number | null;
  target_satisfaction?: number;
  max_energy_balance_error_kwh?: number;
  task_id?: number;
  scenario_type?: string;
  scenario_version_number?: number;
  baseline_delta?: Record<string, number>;
  baseline_change_rate?: Record<string, number | null>;
}
export interface ScenarioComparisonResult extends ScenarioComparisonMetric {
  scenario_version_id: number;
}
export type BaselineDifference = Pick<
  ScenarioComparisonMetric,
  "baseline_delta" | "baseline_change_rate"
>;
export interface SimulationBatchItem {
  id: number;
  scenario_version_id: number;
  task_id?: number | null;
  status: string;
  metrics_json?: ScenarioComparisonMetric | null;
  error_message?: string | null;
}
export interface SimulationBatch {
  id: number;
  enterprise_id: number;
  baseline_scenario_version_id: number;
  status: string;
  request_snapshot_json: SimulationBatchRequest;
  comparison_json?: {
    baseline_scenario_version_id: number;
    metrics: string[];
    items: ScenarioComparisonResult[];
  } | null;
  created_at: string;
  finished_at?: string | null;
  items: SimulationBatchItem[];
}
export interface SimulationBatchRequest {
  site_id?: number;
  enterprise_id: number;
  scenario_version_ids: number[];
  baseline_scenario_version_id: number;
  year: number;
  electricity_price_per_kwh: number;
  feed_in_tariff_per_kwh: number;
  store_hourly_results: boolean;
}
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export interface CarbonMarketScenario {
  id: Id;
  scenario_version_id: Id;
  carbon_price_per_t: number;
  carbon_quota_t: number;
  ccer_quantity_t: number;
  ccer_price_per_t: number;
  green_certificate_quantity: number;
  green_certificate_price: number;
  created_at: string;
}
export interface CarbonMarketIndicator {
  id: number;
  region: string;
  timestamp: string;
  carbon_price_per_t: number | null;
  carbon_quota_t: number | null;
  trading_volume_t: number | null;
  trading_amount_yuan: number | null;
  ccer_volume_t: number | null;
  ccer_price_per_t: number | null;
  ccer_trading_amount_yuan: number | null;
  green_certificate_volume: number | null;
  green_certificate_price: number | null;
  green_certificate_issued_count: number | null;
  green_certificate_traded_count: number | null;
  source: string;
}
export interface CarbonMarketStatisticValue {
  count: number;
  sum: number | null;
  average: number | null;
  min: number | null;
  max: number | null;
}
export interface CarbonMarketStatistics {
  region: string;
  start?: string | null;
  end?: string | null;
  record_count: number;
  quality: "COMPLETE" | "NO_DATA";
  indicators: Record<string, CarbonMarketStatisticValue>;
  records: CarbonMarketIndicator[];
}
export interface CarbonAllowanceResult {
  gross_emission_t: number;
  carbon_quota_t: number;
  quota_balance_t: number;
  quota_surplus_t: number;
  excess_emission_before_offset_t: number;
  excess_emission_after_offset_t: number;
  excess_emission_cost: number;
  quota_surplus_value: number;
}
export interface CCERResult {
  ccer_offset_t: number;
  ccer_cost: number;
  net_carbon_emission_t: number;
}
export interface GreenCertificateResult {
  green_certificate_cost: number;
}
export interface CarbonCostResult
  extends CarbonAllowanceResult, CCERResult, GreenCertificateResult {
  comprehensive_carbon_cost: number;
  physical_energy_balance_changed: boolean;
}
export interface CarbonCostAssessment {
  id: Id;
  scenario_version_id: Id;
  task_id: Id;
  gross_emission_t: number;
  input_snapshot_json: {
    gross_emission_t: number;
    market: Omit<
      CarbonMarketScenario,
      "id" | "scenario_version_id" | "created_at"
    >;
  };
  result_json: CarbonCostResult;
  created_at: string;
}
export interface CarbonMarketBatchComparison {
  batch_id: number;
  baseline_scenario_version_id: number;
  items: {
    scenario_version_id: number;
    task_id?: number | null;
    carbon_market_result?: CarbonCostResult | null;
  }[];
}
export interface CarbonMarketAssessmentCreate {
  scenario_version_id: number;
  task_id: number;
  gross_emission_t?: number;
}
export interface RiskAssessment {
  id: Id;
  scenario_version_id: Id;
  simulation_task_id: Id;
  batch_item_id?: number | null;
  input_snapshot_json: Record<string, unknown>;
  overall_level: RiskLevel;
  results: RiskAssessmentResult[];
  created_at: string;
}
export interface RiskAssessmentResult {
  category: string;
  level: RiskLevel;
  indicator_value: unknown;
  trigger_reason: string;
  recommendation: string;
}
export interface ModelValidationMetrics {
  observed_energy_kwh: number;
  simulated_energy_kwh: number;
  mae_kw: number;
  rmse_kw: number;
  nrmse_pct_rated?: number;
  nrmse_pct_of_dc_capacity?: number;
  energy_error_pct: number;
  correlation: number;
  points?: number;
  paired_records?: number;
}
export interface ModelValidationSummary {
  model: "WIND" | "PV";
  model_version: string;
  dataset: string;
  data_class: string;
  time_range: string;
  metrics: { before: ModelValidationMetrics; after: ModelValidationMetrics };
  parameter_sources: Record<
    string,
    { value: unknown; class: string; source?: string; reason?: string }
  >;
  fallback_used: boolean;
  fallback_code: string;
  limitations: string[];
}
export interface ModelValidationDetail extends ModelValidationSummary {
  series: Array<{
    timestamp: string;
    observed_power_kw: number;
    legacy_simulated_power_kw: number;
    simulated_power_kw: number;
  }>;
}
export type RiskResult = RiskAssessmentResult;
export interface RiskAssessmentCreate {
  scenario_version_id: number;
  simulation_task_id: number;
  batch_item_id?: number;
  simulation_year?: number;
  reduction_rate?: number;
  payback_years?: number;
  price_volatility_pct: number;
  renewable_volatility_pct: number;
  technical_implementation_score: number;
}
export type CarbonMarket = CarbonMarketScenario;
export type ReportStatus = "PENDING" | "GENERATING" | "SUCCESS" | "FAILED";
export interface ReportFile {
  id: Id;
  report_task_id: Id;
  format: "DOCX" | "PDF";
  file_name: string;
  file_size: number;
  checksum: string;
  generated_at: string;
}
export interface ReportSnapshot {
  scenario_version_id: Id;
  simulation_task_id: Id;
  input_snapshot_json: Record<string, unknown>;
  report_data_json: Record<string, unknown>;
  created_at: string;
}
export interface ReportTraceability {
  site_id?: Id;
  scenario_id?: Id;
  scenario_version_id: Id;
  simulation_task_id: Id;
  carbon_market_assessment_id?: Id;
  risk_assessment_id?: Id;
  report_id: Id;
  file_ids: Id[];
}
export interface ReportCreateRequest {
  enterprise_id: Id;
  scenario_version_id: Id;
  simulation_task_id: Id;
  title: string;
  batch_id?: Id;
  accounting_run_id?: Id;
  recommendation_run_id?: Id;
}
export interface ReportRenderRequest {
  formats: ("DOCX" | "PDF")[];
}
export interface ReportTask {
  id: Id;
  enterprise_id: Id;
  scenario_version_id: Id;
  simulation_task_id: Id;
  batch_id?: Id | null;
  accounting_run_id?: Id | null;
  recommendation_run_id?: Id | null;
  title: string;
  status: ReportStatus;
  input_snapshot_json: Record<string, unknown>;
  report_data_json: Record<string, unknown>;
  snapshot_created_at: string;
  files: ReportFile[];
  created_at: string;
  generated_at?: string | null;
  failure_reason?: string | null;
}
export interface SiteOverview {
  site: Site;
  building_count: number;
  device_count: number;
  data_source_count: number;
  energy_system_count: number;
  metering_point_count: number;
  latest_energy: {
    timestamp: string;
    values: { metric: string; value: number; unit: string; quality: string }[];
  } | null;
  latest_carbon_emission_t: number | null;
  data_completeness_rate: number | null;
  anomaly_count: number;
  latest_data_time: string | null;
  data_status: "OK" | "NO_DATA";
}
export interface BuildingOverview {
  building: Building;
  device_count: number;
  energy_system_count: number;
  metering_point_count: number;
  latest_energy: { timestamp: string; values: MetricValue[] } | null;
  latest_carbon_emission_t: number | null;
  data_completeness_rate: number | null;
  anomaly_count: number;
  latest_data_time: string | null;
  data_status: "OK" | "NO_DATA";
}
export interface MetricValue {
  metric: string;
  value: number;
  unit: string;
  quality: string;
}
export interface TrendPoint {
  timestamp: string;
  value: number;
  unit?: string;
  quality?: string;
  quality_status?: string;
  energy_type?: string;
  metric?: string;
  data_source?: string;
}
export interface EnergyTrendResponse {
  building_id: number;
  timezone: string;
  data_status: "OK" | "NO_DATA";
  items: TrendPoint[];
}
export interface CarbonTrendResponse {
  data_status: "OK" | "NO_DATA";
  total_emission_t: number | null;
  scope: Record<string, number>;
  energy: Record<string, number>;
  factor_sources: string[];
  trend: { timestamp: string; emission_t: number }[];
}
export interface TelemetryResponse {
  object_id: string;
  object_type: string;
  metric: string;
  timezone: string;
  data_status: "OK" | "NO_DATA";
  data: TrendPoint[];
}
export interface MeteringTimeseries extends TelemetryResponse {
  energy_type: string;
  unit: string;
  start_time?: string;
  end_time?: string;
}
export interface DeviceOverview {
  device: Device;
  metric_count: number;
  latest_timestamp: string | null;
  latest_quality: string | null;
  data_status: "OK" | "NO_DATA";
}
export interface DataQuality {
  data_source_id: number;
  total_records: number;
  valid_records: number;
  quarantined_records: number;
  warning_records: number;
  quality_rate: number;
  by_stage: Record<string, number>;
}
export type MeasureType =
  | "PV"
  | "WIND"
  | "STORAGE"
  | "HVAC"
  | "LIGHTING"
  | "EV_CHARGER"
  | "GREEN_POWER";
export interface PVConfig {
  capacity_kw: number;
  tilt_deg: number;
  azimuth_deg: number;
  inverter_efficiency: number;
  irradiance_mode: "GHI" | "POA";
  noct_c: number;
  temperature_coefficient_per_c: number;
  performance_ratio: number;
  export_limit_kw?: number;
}
export interface WindCurvePoint {
  wind_speed_m_s: number;
  power_fraction: number;
}
export interface WindConfig {
  rated_power_kw: number;
  cut_in_speed_m_s: number;
  rated_speed_m_s: number;
  cut_out_speed_m_s: number;
  power_curve?: WindCurvePoint[];
}
export interface StorageConfig {
  capacity_kwh: number;
  max_charge_kw: number;
  max_discharge_kw: number;
  charge_efficiency: number;
  discharge_efficiency: number;
  soc_initial: number;
  soc_min: number;
  soc_max: number;
  strategy: "PV_SELF_CONSUMPTION" | "PEAK_VALLEY_ARBITRAGE";
}
export interface HVACConfig {
  saving_rate: number;
  load_share: number;
}
export interface LightingConfig {
  saving_rate: number;
  load_share: number;
}
export interface EVChargerConfig {
  charger_count: number;
  rated_power_kw_per_charger: number;
  utilization_rate: number;
  daily_energy_kwh: number;
  charging_start_hour: number;
  charging_end_hour: number;
  arrival_hour: number;
  departure_hour: number;
  load_curve?: number[];
}
export interface GreenPowerConfig {
  purchase_share: number;
  purchase_kwh?: number;
  emission_factor_kg_per_kwh: number;
  premium_per_kwh: number;
}
export interface SimulationMeasure {
  measure_type: MeasureType;
  enabled: boolean;
  start_year: number;
  end_year?: number | null;
  parameters_json:
    | PVConfig
    | WindConfig
    | StorageConfig
    | HVACConfig
    | LightingConfig
    | EVChargerConfig
    | GreenPowerConfig;
}
export interface HourlySimulationRequest {
  site_id?: number;
  scenario_id: number;
  scenario_version_id?: number;
  year: number;
  start_time?: string;
  end_time?: string;
  electricity_price_per_kwh: number;
  feed_in_tariff_per_kwh: number;
  store_hourly_results: boolean;
  weather_site_id?: number;
  temporary_measures?: Omit<ScenarioMeasure, "id" | "scenario_id">[];
}
export interface HourlySimulationPoint {
  timestamp: string;
  load_base_kwh: number;
  hvac_saved_kwh: number;
  lighting_saved_kwh: number;
  load_after_saving_kwh: number;
  ev_charging_load_kwh: number;
  pv_generation_kwh: number;
  wind_generation_kwh: number;
  renewable_generation_kwh: number;
  storage_charge_kwh: number;
  storage_discharge_kwh: number;
  storage_soc_kwh: number;
  grid_power_kwh: number;
  renewable_export_kwh: number;
  curtailed_renewable_kwh: number;
  curtailed_pv_kwh: number;
  carbon_emission_t: number;
  green_power_carbon_reduction_t: number;
  electricity_cost: number;
  feed_in_revenue: number;
  energy_balance_error_kwh: number;
}
export interface HourlySimulationSummary {
  task_id: number;
  scenario_id: number;
  scenario_version_id?: number | null;
  year: number;
  hours: number;
  load_base_kwh: number;
  energy_saved_kwh: number;
  pv_generation_kwh: number;
  wind_generation_kwh: number;
  renewable_generation_kwh: number;
  grid_power_kwh: number;
  storage_charge_kwh: number;
  storage_discharge_kwh: number;
  carbon_emission_t: number;
  electricity_cost: number;
  feed_in_revenue: number;
  green_power_carbon_reduction_t: number;
  ev_charging_load_kwh: number;
  renewable_export_kwh: number;
  curtailed_renewable_kwh: number;
}
export interface HourlySimulationResult {
  summary: HourlySimulationSummary;
  results: HourlySimulationPoint[];
}
export interface AnnualSimulationRequest {
  site_id?: number;
  scenario_id: number;
  scenario_version_id?: number;
  electricity_price_per_kwh: number;
  feed_in_tariff_per_kwh: number;
}
export interface AnnualSimulationResult {
  task: {
    id: number;
    scenario_id: number;
    status: string;
    summary_json?: Record<string, unknown> | null;
    started_at?: string | null;
    finished_at?: string | null;
    error_message?: string | null;
  };
  results: {
    year: number;
    electricity_base_kwh: number;
    electricity_after_saving_kwh: number;
    grid_power_kwh: number;
    pv_generation_kwh: number;
    carbon_emission_t: number;
    carbon_reduction_t: number;
    investment: number;
    annual_benefit: number;
  }[];
}
export interface LongTermAnnualPoint {
  year: number;
  energy_consumption_kwh: number;
  renewable_generation_kwh: number;
  grid_import_kwh: number;
  gross_emission_t: number;
  net_emission_t: number;
  carbon_reduction_t: number;
  reduction_rate: number;
  carbon_quota_t: number;
  quota_balance_t: number;
  annual_investment: number;
  cumulative_investment: number;
  operating_cost: number;
  carbon_cost: number;
  grid_factor_kg_per_kwh: number;
  commissioned_measures: string[];
}
export interface LongTermPathRequest {
  site_id?: number;
  scenario_version_id: number;
  baseline_task_id?: number;
  start_year: number;
  end_year: number;
  target_peak_year: number;
  target_neutral_year: number;
  annual_load_growth_rate: number;
  comprehensive_energy_target_rate?: number;
  carbon_quota_t: number;
  annual_quota_change_rate: number;
  annual_grid_factor_change_rate: number;
  electricity_price_per_kwh: number;
  annual_price_change_rate: number;
  carbon_price_per_t: number;
  neutrality_threshold_t: number;
  measures?: ScenarioMeasure[];
}
export interface LongTermPathRun {
  id: number;
  enterprise_id: number;
  scenario_version_id: number;
  baseline_task_id?: number | null;
  status: string;
  input_snapshot_json: LongTermPathRequest & { resolved_measures?: ScenarioMeasure[] };
  result_snapshot_json: {
    annual: LongTermAnnualPoint[];
    actual_peak_year: number;
    peak_emission_t: number;
    actual_neutral_year?: number | null;
    neutrality_status: string;
    target_peak_met: boolean;
    target_neutral_met: boolean;
    comprehensive_energy_target_met?: boolean | null;
    emission_at_end_t: number;
    cumulative_reduction_t: number;
    cumulative_investment: number;
    cumulative_energy_cost: number;
    gap_analysis: {
      targets_met: boolean;
      target_peak_year: number;
      actual_peak_year: number;
      peak_delay_years: number;
      target_neutral_year: number;
      actual_neutral_year?: number | null;
      target_year_remaining_emission_t: number;
      neutrality_gap_t: number;
      neutrality_threshold_t: number;
      annual_quota_gaps: { year: number; gap_t: number }[];
      max_quota_gap_t: number;
      reasons: { code: string; title: string; evidence: string }[];
      recommendations: { stage: string; items: string[] }[];
      success_factors: string[];
    };
    key_milestones: { year: number; measures: string[] }[];
    baseline: Record<string, number | string>;
  };
  created_at: string;
}
export interface StrengthenedPathRequest {
  pv_annual_addition_kw: number;
  wind_annual_addition_kw: number;
  storage_expansion_year?: number;
  storage_expansion_kwh: number;
  additional_hvac_saving_rate: number;
  additional_lighting_saving_rate: number;
  green_power_ratio: number;
  annual_ccer_t: number;
  annual_grid_factor_change_rate?: number;
}
export interface WeatherSite {
  id: number;
  enterprise_id: number;
  name: string;
  latitude?: number | null;
  longitude?: number | null;
  timezone: string;
  source?: string | null;
  created_at: string;
}
export interface QualitySummary {
  observed_points: number;
  expected_points: number;
  missing_points: number;
  completeness_rate: number;
  quality: string;
}
export interface MarketPrice {
  timestamp: string;
  purchase_price_per_kwh: number;
  feed_in_tariff_per_kwh: number;
  source?: string | null;
}
export interface GridFactor {
  timestamp: string;
  region: string;
  factor_kg_per_kwh: number;
  source?: string | null;
  version: string;
}
export interface PageResult<T> {
  items: T[];
  total?: number;
}
export interface SystemHealth {
  application_status: "UP" | "DEGRADED";
  backend_version: string;
  api_version: string;
  database_status: "UP" | "DOWN";
  database_type: string;
  alembic_revision: string | null;
  alembic_head: string;
  is_head: boolean;
  current_time: string;
  uptime_seconds: number | null;
}
export interface SystemVersion extends Pick<
  SystemHealth,
  | "backend_version"
  | "api_version"
  | "alembic_revision"
  | "alembic_head"
  | "is_head"
  | "database_type"
> {
  frontend_version: string;
}
export interface ProviderStatus {
  provider:
    | "WeatherProvider"
    | "ElectricityPriceProvider"
    | "GridEmissionFactorProvider"
    | "GreenPowerService"
    | string;
  dynamic_data_available: boolean;
  record_count: number;
  latest_data_time: string | null;
  range_start: string | null;
  range_end: string | null;
  source: string | null;
  using_fallback: boolean;
}
export interface DataSourceStatus {
  id: number;
  enterprise_id: number;
  name: string;
  source_type: string;
  status: string;
  last_sync_at: string | null;
  last_success_at: string | null;
  last_failure_at: string | null;
  last_failure_reason: string | null;
  quality_rate: number | null;
  valid_records: number;
  rejected_records: number;
  warning_records: number;
  supports_connection_test: boolean;
  supports_manual_sync: boolean;
}
export interface SystemTaskSummary {
  task_type: "SIMULATION" | "RECOMMENDATION" | "BATCH" | "RISK" | "REPORT";
  id: number;
  status: string;
  created_at: string | null;
  finished_at: string | null;
  failure_reason: string | null;
  scenario_version_id?: number;
  simulation_task_id?: number;
}
export interface RuntimeAlert {
  level: "LOW" | "MEDIUM" | "HIGH";
  category: string;
  message: string;
  occurred_at: string | null;
}
export interface TraceabilityNode {
  key: string;
  type: string;
  id: number;
  label: string;
  status: string | null;
}
export interface TraceabilityEdge {
  from: string;
  to: string;
}
export interface SystemTraceability {
  nodes: TraceabilityNode[];
  edges: TraceabilityEdge[];
}
export interface SystemOverview {
  health: SystemHealth;
  data_source_count: number;
  normal_data_source_count: number;
  abnormal_data_source_count: number;
  providers: ProviderStatus[];
  latest_system_exception_time: string | null;
  alerts: RuntimeAlert[];
  configuration: {
    default_timezone: string;
    default_emission_factor_mode: string;
    default_electricity_price_mode: string;
    file_storage_type: string;
    api_base_configuration: string;
  };
  models: string[];
}
export interface DashboardCarbon {
  total_t: number | null;
  scope1_t: number | null;
  scope2_t: number | null;
  month_t: number | null;
  year_t: number | null;
  per_area_kg_m2: number | null;
  per_capita_t: number | null;
  trend: { timestamp: string; emission_t: number }[];
  energy: Record<string, number>;
}
export interface DashboardEnergy {
  total_energy_kwh: number | null;
  grid_kwh: number | null;
  pv_kwh: number | null;
  wind_kwh: number | null;
  renewable_rate: number | null;
  hourly: HourlySimulationPoint[];
  task_id: number | null;
}
export interface DashboardMeasure {
  type: MeasureType;
  enabled: boolean;
  summary: string;
  value: number | null;
  unit?: string;
}
export interface DashboardRecommendation {
  profile: RecommendationProfile;
  score: number;
  measures: string[];
  reduction_t: number | null;
  investment: number | null;
  payback_years: number | null;
}
export interface DashboardScenario extends ScenarioComparisonResult {
  name: string;
  type: string;
  baseline: boolean;
}
export interface DashboardMarket {
  assessment: CarbonCostAssessment | null;
  statistics: CarbonMarketStatistics | null;
}
export interface DashboardRisk {
  run: RiskAssessment | null;
  high: number;
  medium: number;
  low: number;
}
export interface DashboardSystemStatus {
  overview: SystemOverview | null;
  tasks: SystemTaskSummary[];
}
export interface DashboardOverview {
  site: Site;
  site_overview: SiteOverview | null;
  buildings: Building[];
  carbon: DashboardCarbon;
  energy: DashboardEnergy;
  measures: DashboardMeasure[];
  recommendations: DashboardRecommendation[];
  scenarios: DashboardScenario[];
  market: DashboardMarket;
  risk: DashboardRisk;
  system: DashboardSystemStatus;
}
