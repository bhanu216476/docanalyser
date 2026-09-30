import argparse
import json
import sys
from pathlib import Path

def apply_quality_gate(candidate_path: str, baseline_path: str, thresholds_path: str, summary_output: str):
    with open(candidate_path, "r") as f:
        candidate = json.load(f)
        
    with open(baseline_path, "r") as f:
        baseline = json.load(f)
        
    with open(thresholds_path, "r") as f:
        thresholds = json.load(f)["metrics"]
        
    candidate_metrics = candidate.get("metrics", {})
    baseline_metrics = baseline.get("metrics", {})
    
    failures = []
    summary_lines = [
        "| Metric | Baseline | Candidate | Diff | Status |",
        "|--------|----------|-----------|------|--------|"
    ]
    
    for metric, config in thresholds.items():
        base_val = baseline_metrics.get(metric)
        cand_val = candidate_metrics.get(metric)
        
        if base_val is None or cand_val is None:
            continue
            
        diff = cand_val - base_val
        status = "✅ Pass"
        
        if config["type"] == "relative":
            if base_val > 0:
                rel_drop = (base_val - cand_val) / base_val
                if rel_drop > config["limit"]:
                    status = "❌ Fail"
                    failures.append(f"{metric} dropped by {rel_drop:.1%} (limit {config['limit']:.1%})")
        elif config["type"] == "absolute":
            abs_drop = base_val - cand_val
            if abs_drop > config["limit"]:
                status = "❌ Fail"
                failures.append(f"{metric} dropped by {abs_drop:.3f} (limit {config['limit']:.3f})")
                
        diff_str = f"{diff:+.3f}"
        summary_lines.append(f"| {metric} | {base_val:.3f} | {cand_val:.3f} | {diff_str} | {status} |")
        
    with open(summary_output, "w") as f:
        if failures:
            f.write("### ❌ Quality Gate Failed\n\n")
            for fail in failures:
                f.write(f"- {fail}\n")
        else:
            f.write("### ✅ Quality Gate Passed\n\n")
            
        f.write("\n" + "\n".join(summary_lines) + "\n")
        
    if failures:
        print("Quality gate failed!")
        for fail in failures:
            print(f" - {fail}")
        sys.exit(1)
    else:
        print("Quality gate passed!")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--thresholds", required=True)
    parser.add_argument("--summary-output", required=True)
    args = parser.parse_args()
    
    apply_quality_gate(args.candidate, args.baseline, args.thresholds, args.summary_output)
