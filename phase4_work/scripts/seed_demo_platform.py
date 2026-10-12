"""Build the deterministic unified demo park in the configured development DB."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if os.getenv("DEMO_MODE") != "1":
        raise RuntimeError("set DEMO_MODE=1 to acknowledge insertion of demonstration data")
    database_url = os.getenv("DATABASE_URL") or os.getenv("DEV_DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL or DEV_DATABASE_URL is required")
    if "carbon_neutral_dev" not in database_url:
        raise RuntimeError("the demo initializer only accepts the carbon_neutral_dev database")
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": database_url,
           "ALLOW_SYNTHETIC_VALIDATION": "1"}
    for script in ("generate_demo_dataset.py", "load_demo_case.py", "run_demo_full_chain.py", "seed_final_acceptance_demo.py"):
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=ROOT,
                       env=env, check=True)
    print("统一示范园区初始化完成：智慧低碳示范园区（数据性质：示范仿真数据）")


if __name__ == "__main__":
    main()
