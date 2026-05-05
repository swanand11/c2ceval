import pandas as pd
from tqdm import tqdm
import os
import time
import multiprocessing as mp

from utils.clone import clone_repo
from utils.analysis import analyze_code
from utils.readme_parser import extract_team_info
from utils.llm import get_architecture_score

# ===== GLOBAL CONCURRENCY CONTROL =====
manager = mp.Manager()
llm_semaphore = manager.Semaphore(3)  # Max 3 concurrent LLM calls
stats = manager.dict()
stats["total_processed"] = 0
stats["total_timeout"] = 0
stats["llm_calls_made"] = 0
stats["llm_calls_skipped"] = 0
start_time = time.time()


# ===== MONITORING =====
def log_stats():
    elapsed = time.time() - start_time
    if elapsed > 0:
        rate = stats["total_processed"] / elapsed * 60
        print(f"\n📊 STATS: {stats['total_processed']} repos processed in {elapsed:.0f}s")
        print(f"   📈 Rate: {rate:.2f} repos/min")
        print(f"   ⏱️  Timeouts: {stats['total_timeout']}")
        print(f"   🤖 LLM calls: {stats['llm_calls_made']} made, {stats['llm_calls_skipped']} skipped")
        timeout_pct = (stats["total_timeout"] / stats["total_processed"] * 100) if stats["total_processed"] > 0 else 0
        print(f"   ⚠️  Timeout rate: {timeout_pct:.1f}%\n")


# ===== LLM CALL WRAPPER =====
def get_architecture_score_safe(text):
    """Wrap LLM call with semaphore to limit concurrency."""
    with llm_semaphore:
        return get_architecture_score(text)


# ===== HEURISTIC-BASED SKIP LOGIC =====
def should_skip_llm(heuristic_score):
    """
    Skip LLM for obvious cases:
    - Score > 90: Already excellent
    """
    return heuristic_score > 90


# ===== DETERMINISTIC FALLBACK SCORE =====
def get_fallback_arch_score(heuristic_score):
    """Assign architecture score based on heuristic if skipping LLM."""
    if heuristic_score > 90:
        return 90, "Skipped (excellent heuristic)"
    else:
        # Should not reach here, but fallback just in case
        return 50, "Skipped (unknown reason)"


# ===== TIMEOUT RUNNER (PROCESS-BASED) =====
def run_with_timeout(fn, args=(), timeout=60):
    """Run a function in a separate process so it can be killed on timeout."""

    def wrapper(q, fn, args):
        try:
            start = time.perf_counter()
            result = fn(*args)
            elapsed = time.perf_counter() - start
            q.put(("ok", result, elapsed))
        except Exception as e:
            q.put(("err", repr(e), None))

    q = mp.Queue()
    p = mp.Process(target=wrapper, args=(q, fn, args))
    p.start()
    p.join(timeout)

    if p.is_alive():
        p.terminate()
        p.join()
        raise TimeoutError(f"{fn.__name__} timed out after {timeout}s")

    if q.empty():
        raise RuntimeError(f"{fn.__name__} finished but returned nothing")

    status, value, elapsed = q.get()

    if status == "err":
        raise RuntimeError(value)

    print(f"  ⏱️ {fn.__name__} took {elapsed:.2f}s")
    return value


# ===== REPO SUMMARIZER =====
def summarize_repo(repo_path):
    summary = []
    for root, _, files in os.walk(repo_path):
        for file in files[:5]:
            if file.endswith((".py", ".js", ".ts", ".java")):
                try:
                    with open(
                        os.path.join(root, file),
                        "r",
                        encoding="utf-8",
                        errors="ignore",
                    ) as f:
                        summary.append(f.read(500))
                except Exception:
                    continue
    return "\n".join(summary[:5])


# -------------------------------
# Core pipeline per repo
# -------------------------------
def process_repo(repo_url):
    print(f"\n🔗 Processing: {repo_url}")

    # ---- Clone ----
    print("  🔄 Cloning...")
    t0 = time.perf_counter()
    repo_path = run_with_timeout(clone_repo, args=(repo_url,), timeout=30)
    print(f"  ✅ Clone done in {time.perf_counter() - t0:.2f}s")

    if not repo_path:
        raise ValueError("Clone returned None")

    # ---- Heuristic analysis ----
    print("  🔍 Analyzing code...")
    t0 = time.perf_counter()
    heuristic_score = run_with_timeout(analyze_code, args=(repo_path,), timeout=60)
    print(f"  ✅ Analysis done in {time.perf_counter() - t0:.2f}s")

    # ---- Team info ----
    print("  📄 Extracting team info...")
    t0 = time.perf_counter()
    team_data = run_with_timeout(extract_team_info, args=(repo_path,), timeout=30)
    print(f"  ✅ Team info done in {time.perf_counter() - t0:.2f}s")

    # ---- LLM scoring (with heuristic skip logic) ----
    print("  🤖 Scoring architecture...")
    
    if should_skip_llm(heuristic_score):
        # Skip LLM for obvious cases
        arch_score, reason = get_fallback_arch_score(heuristic_score)
        print(f"  ⏭️  Skipped LLM: {reason}")
        stats["llm_calls_skipped"] += 1
    else:
        # Call LLM with reduced prompt size (max 2000 chars total)
        arch_text = team_data["architecture_text"][:1000]
        repo_summary = summarize_repo(repo_path)[:1000]
        combined = arch_text + "\n" + repo_summary

        t0 = time.perf_counter()
        arch_score, reason = run_with_timeout(
            get_architecture_score_safe,
            args=(combined,),
            timeout=120,
        )
        elapsed = time.perf_counter() - t0
        print(f"  🤖 Architecture score: {arch_score} ({reason}) [{elapsed:.2f}s]")
        stats["llm_calls_made"] += 1

    # ---- Final score ----
    total_score = round((heuristic_score + arch_score) / 2, 2)

    return {
        "repo": repo_url,
        "team_name": team_data.get("team_name"),
        "all_women": team_data.get("all_women"),
        "all_junior": team_data.get("all_junior"),
        "heuristic_score": heuristic_score,
        "architecture_score": arch_score,
        "total_score": total_score,
    }


# -------------------------------
# Main runner
# -------------------------------
def run():
    if os.path.exists("results.csv"):
        os.remove("results.csv")

    df = pd.read_csv("input.csv")
    file_exists = False

    try:
        for i, (_, row) in enumerate(tqdm(df.iterrows(), total=len(df))):
            repo_url = row["repo"]
            print(f"\n[{i+1}/{len(df)}]")

            try:
                result = process_repo(repo_url)

                pd.DataFrame([result]).to_csv(
                    "results.csv",
                    mode="a" if file_exists else "w",
                    header=not file_exists,
                    index=False,
                )

                file_exists = True
                stats["total_processed"] += 1
                print(f"  ✅ Done — total score: {result['total_score']}")

            except TimeoutError as e:
                print(f"  ⏱️ Timeout: {e} — skipping")
                stats["total_timeout"] += 1
                stats["total_processed"] += 1

            except Exception as e:
                print(f"  ❌ Failed: {e} — skipping")
                stats["total_processed"] += 1

            # Log stats every 10 repos
            if (stats["total_processed"]) % 10 == 0:
                log_stats()

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user. Partial results saved.")

    # Final stats
    log_stats()
    print(
        f"\n✅ Finished. results.csv "
        f"{'generated' if file_exists else 'NOT generated — all repos failed'}"
    )


# -------------------------------
# Entry point
# -------------------------------
if __name__ == "__main__":
    run()