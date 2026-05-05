import os

def analyze_code(repo_path):
    total_files = 0
    total_lines = 0
    complexity_score = 0
    test_files = 0

    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith((".py", ".js", ".ts", ".java", ".cpp")):
                total_files += 1
                filepath = os.path.join(root, file)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        total_lines += len(lines)

                        for line in lines:
                            if any(k in line for k in ["if", "for", "while", "case"]):
                                complexity_score += 1

                    if "test" in file.lower():
                        test_files += 1

                except:
                    continue

    test_coverage = test_files / total_files if total_files else 0

    heuristic_score = (
        min(total_files / 50, 1) * 20 +
        min(total_lines / 5000, 1) * 20 +
        min(complexity_score / 1000, 1) * 30 +
        test_coverage * 30
    )

    return round(heuristic_score, 2)