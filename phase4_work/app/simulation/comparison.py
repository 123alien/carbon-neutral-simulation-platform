class ScenarioComparator:
    @staticmethod
    def compare(summaries):
        return sorted([
            {
                "name": s.name,
                "peak_year": s.peak_year,
                "neutral_year": s.neutral_year,
                "cumulative_emission_t": round(s.cumulative_emission_t, 3),
                "cumulative_investment": round(s.cumulative_investment, 2),
                "cumulative_benefit": round(s.cumulative_benefit, 2),
            }
            for s in summaries
        ], key=lambda x: x["cumulative_emission_t"])
