"""Seed InsightFlow with the bundled Build Battle dataset.

Usage: python scripts/seed.py [backend_url]
Default backend URL: http://127.0.0.1:8000
"""
import sys
import time
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "BuildBattle_2026_Customer_Feedback_Dataset.csv"


def multipart_post(url: str, file_path: Path, fields: dict[str, str]) -> tuple[int, bytes]:
    boundary = "----insightflowseed"
    body = b""
    for k, v in fields.items():
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n"
        ).encode()
    body += (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{file_path.name}\"\r\nContent-Type: text/csv\r\n\r\n"
    ).encode()
    body += file_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.status, resp.read()


def main() -> None:
    with urllib.request.urlopen(f"{BASE}/api/health", timeout=10) as resp:
        assert resp.status == 200, "Backend is not running"
    # Wait for any in-flight analysis job so the import doesn't race it.
    for _ in range(60):
        with urllib.request.urlopen(f"{BASE}/api/analytics/job", timeout=10) as resp:
            job = __import__("json").loads(resp.read())
        if job.get("status") not in ("pending", "running"):
            break
        print(f"  waiting for in-flight job ({job.get('status')}) …")
        time.sleep(3)
    print(f"Importing {CSV_PATH.name} …")
    status, raw = multipart_post(f"{BASE}/api/feedback/import", CSV_PATH, {"mode": "replace"})
    print(f"HTTP {status}: {raw.decode()[:300]}")
    print("Waiting for analysis to finish …")
    for _ in range(60):
        with urllib.request.urlopen(f"{BASE}/api/analytics/job", timeout=10) as resp:
            job = __import__("json").loads(resp.read())
        print(f"  status={job.get('status')} processed={job.get('processed')}/{job.get('total')}")
        if job.get("status") in ("completed", "failed"):
            break
        time.sleep(3)
    print("Seed complete.")


if __name__ == "__main__":
    main()
