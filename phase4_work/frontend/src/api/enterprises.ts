import { http } from "./http";
import type { Enterprise } from "@/types";

export interface EnterpriseCreate {
  name: string;
  region?: string | null;
  industry?: string | null;
  building_area?: number | null;
  population?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  base_year: number;
}

export const enterprisesApi = {
  list: () => http.get<never, Enterprise[]>("/api/enterprises"),
  create: (payload: EnterpriseCreate) => http.post<never, Enterprise>("/api/enterprises", payload),
};
