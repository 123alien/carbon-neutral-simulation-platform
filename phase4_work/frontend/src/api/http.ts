import axios, { AxiosError } from "axios";
import { ElMessage } from "element-plus";
import type { ApiError } from "@/types";
export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});
const errorMessages: Record<string, string> = {
  "hourly load data is required to validate recommendations":
    "当前园区缺少用于推荐验证的小时负荷数据，请先完成示范数据初始化或切换到湖北经济学院园区。",
  "no hourly load data found":
    "当前园区在所选年度没有小时负荷数据，请调整年度或先完成数据接入。",
  "electricity factor coverage is incomplete":
    "所选年度的电力排放因子覆盖不完整，请补齐排放因子后重试。",
  "enterprise not found": "当前园区关联的企业不存在，请重新选择园区。",
  "recommendation run not found": "未找到对应的推荐记录，请刷新后重新生成。",
};
function localizeError(message: string, status?: number) {
  const matched = Object.entries(errorMessages).find(([key]) =>
    message.toLowerCase().includes(key.toLowerCase()),
  );
  if (matched) return matched[1];
  if (message === "Network Error") return "无法连接后端服务，请检查服务是否启动。";
  if (message.toLowerCase().includes("timeout")) return "请求超时，请稍后重试。";
  if (status === 401) return "登录状态已失效，请重新登录。";
  if (status === 404) return "请求的数据不存在或已被删除。";
  if (status && status >= 500) return "后端服务处理失败，请稍后重试。";
  return message;
}
http.interceptors.request.use((config) => {
  config.headers.set("X-Client-Version", "V1.0.0-beta.15");
  return config;
});
http.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError<{ detail?: string; message?: string }>) => {
    const rawMessage =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "服务请求失败";
    const normalized: ApiError = {
      message: localizeError(rawMessage, error.response?.status),
      status: error.response?.status,
      code: error.code,
      details: error.response?.data,
    };
    if (!error.config?.headers?.get("X-Silent-Error"))
      ElMessage.error(normalized.message);
    return Promise.reject(normalized);
  },
);
export const silentConfig = { headers: { "X-Silent-Error": "1" } };
