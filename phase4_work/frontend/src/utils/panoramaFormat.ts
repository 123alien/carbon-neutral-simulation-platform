/** Display-only formatting; never changes the underlying business metrics. */
export const formatPanoramaNumber = (value: number | null, digits = 1) =>
  value === null || !Number.isFinite(value)
    ? "暂无数据"
    : value.toLocaleString("zh-CN", { maximumFractionDigits: digits });
export const panoramaTypeName = (value: string) =>
  ({
    PV: "光伏",
    WIND: "风电",
    STORAGE: "储能",
    HVAC: "空调",
    LIGHTING: "照明",
    EV_CHARGER: "充电桩",
    ELECTRIC_METER: "电表",
    WATER_METER: "水表",
    OFFICE: "办公建筑",
    ADMIN: "行政建筑",
    TEACHING: "教学建筑",
    LAB: "实验建筑",
    SERVICE: "综合服务建筑",
  })[value.toUpperCase()] || value;
