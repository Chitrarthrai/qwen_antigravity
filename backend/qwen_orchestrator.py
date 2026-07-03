#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import json
import urllib.request
import re

# Dynamic Paths Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "backend" else SCRIPT_DIR
PARENT_DIR = os.path.dirname(ROOT_DIR)

QWEN_DIR = SCRIPT_DIR
RESUME_PATH = os.path.join(PARENT_DIR, "overleaf", "main.tex")
FINDINGS_PATH = os.path.join(ROOT_DIR, "qwen_findings.md")
OLLAMA_MODEL = "qwen2.5:14b"

def query_qwen(prompt, json_format=False):
    """Query the local Qwen model using Ollama API."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 4096
        }
    }
    if json_format:
        payload["format"] = "json"
        
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            res_data = response.read().decode('utf-8')
            res_json = json.loads(res_data)
            return res_json.get("response", "").strip()
    except Exception as e:
        print(f"Error querying Qwen: {e}")
        return None

def trigger_antigravity(findings_file, prompt_message):
    """Invokes the Antigravity CLI to trigger a new agent chat session in the IDE."""
    print("\n[Orchestrator] 🚨 Triggering Antigravity Agent Session...")
    cmd = [
        "/usr/bin/antigravity", "chat",
        "-m", "agent",
        "-a", findings_file,
        prompt_message
    ]
    try:
        # Run asynchronously so the command line returns immediately while opening the chat session
        subprocess.Popen(cmd)
        print("[Orchestrator] Antigravity chat triggered successfully!")
    except Exception as e:
        print(f"[Orchestrator] Error triggering Antigravity CLI: {e}")

def run_latex_validation():
    """Runs the LaTeX validator script."""
    print("\n[Orchestrator] Running LaTeX validation checks...")
    validator_script = os.path.join(QWEN_DIR, "validate_latex.py")
    
    result = subprocess.run(
        ["python3", validator_script, RESUME_PATH],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("[Orchestrator] ❌ LaTeX Validation Failed.")
        # Create the findings report
        findings = f"""# Qwen Automated Flow: LaTeX Validation Failure

The local validation pipeline failed. The resume file at `{RESUME_PATH}` has syntax or structural errors.

## Execution Output:
```
{result.stdout}
{result.stderr}
```

## Instructions for Antigravity:
Please review the LaTeX error output, open [main.tex](file://{RESUME_PATH}), fix any unmatched braces or environments, and ensure it compiles successfully.
"""
        with open(FINDINGS_PATH, "w", encoding="utf-8") as f:
            f.write(findings)
            
        trigger_antigravity(
            FINDINGS_PATH,
            f"The LaTeX resume has syntax/structural errors. Please open {RESUME_PATH}, analyze the validation errors in the attached findings file, and fix them."
        )
        return False
        
    print("[Orchestrator] ✅ LaTeX validation passed successfully.")
    return True

def run_ats_optimization(jd_text=None, jd_file=None):
    """Runs the ATS Tailoring/Optimization pipeline."""
    print("\n[Orchestrator] Running ATS Resume Tailoring...")
    opt_script = os.path.join(QWEN_DIR, "ats_optimizer.py")
    
    cmd = ["python3", opt_script]
    if jd_file:
        cmd.extend(["--jd", jd_file])
    elif jd_text:
        cmd.extend(["--text", jd_text])
        
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
        
    # Check if optimize script returned success and if the resume is still valid LaTeX
    if result.returncode != 0 or "failed" in result.stdout.lower():
        print("[Orchestrator] ❌ ATS Optimization Script Failed.")
        findings = f"""# Qwen Automated Flow: ATS Optimization Failure

The ATS optimization script encountered an error or generated invalid outputs.

## Script Output:
```
{result.stdout}
{result.stderr}
```

## Instructions for Antigravity:
Please analyze the execution logs, check [main.tex](file://{RESUME_PATH}), and manually optimize/repair the sections as needed to align with the job description.
"""
        with open(FINDINGS_PATH, "w", encoding="utf-8") as f:
            f.write(findings)
            
        trigger_antigravity(
            FINDINGS_PATH,
            "The ATS Resume Optimization script failed or returned invalid outputs. Please inspect the logs and resolve the issue."
        )
        return False
        
    # Validate LaTeX structure after optimization
    return run_latex_validation()

def run_ats_scoring(jd_text=None, jd_file=None):
    """Runs the ATS Scoring script and checks if score meets target threshold."""
    print("\n[Orchestrator] Running ATS Resume Scoring...")
    scorer_script = os.path.join(QWEN_DIR, "ats_scorer.py")
    
    cmd = ["python3", scorer_script]
    if jd_file:
        cmd.extend(["--jd", jd_file])
    elif jd_text:
        cmd.extend(["--text", jd_text])
        
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout)
    
    # Read the generated report to verify score
    report_path = os.path.join(ROOT_DIR, "ats_score_report.md")
    if not os.path.exists(report_path):
        print("[Orchestrator] ❌ ATS Score report was not generated.")
        return False
        
    with open(report_path, "r", encoding="utf-8") as f:
        report_content = f.read()
        
    # Extract score using regex e.g. "Overall ATS Score: **85/100**"
    match = re.search(r"Overall ATS Score:\s*\*\*(\d+)/100\*\*", report_content)
    score = int(match.group(1)) if match else 0
    print(f"[Orchestrator] Parsed Score: {score}/100")
    
    if score < 90:
        print(f"[Orchestrator] ⚠️ ATS Score ({score}) is below target threshold of 90/100.")
        findings = f"""# Qwen Automated Flow: ATS Score Below Target

The candidate's resume scored **{score}/100**, which is below our target of 90/100.

## Recommendations from local Qwen scanner:
Refer to the recommendations in [ats_score_report.md](file://{report_path}).

## Instructions for Antigravity:
Please read the recommendations in [ats_score_report.md](file://{report_path}), and edit [main.tex](file://{RESUME_PATH}) to address them (such as expanding metrics, adding missing keywords, or refining layout) until the score is 90 or above.
"""
        with open(FINDINGS_PATH, "w", encoding="utf-8") as f:
            f.write(findings)
            
        trigger_antigravity(
            FINDINGS_PATH,
            f"The ATS Resume Score is only {score}/100. Please review the recommendations in {report_path} and optimize the resume at {RESUME_PATH} to improve the score."
        )
        return False
        
    print(f"[Orchestrator] 🎉 Success! ATS Score is {score}/100 (>= 90).")
    return True

def main():
    parser = argparse.ArgumentParser(description="Qwen-to-Antigravity Task Orchestrator")
    parser.add_argument(
        "--task",
        choices=["validate-resume", "optimize-resume", "score-resume", "run-custom"],
        required=True,
        help="The automated task to run."
    )
    parser.add_argument("--jd", type=str, help="Path to job description file (for optimize/score-resume)")
    parser.add_argument("--text", type=str, help="Raw job description text (for optimize/score-resume)")
    parser.add_argument("--prompt", type=str, help="Custom prompt for Qwen (for run-custom)")
    
    args = parser.parse_args()
    
    if args.task == "validate-resume":
        run_latex_validation()
    elif args.task == "optimize-resume":
        run_ats_optimization(jd_text=args.text, jd_file=args.jd)
    elif args.task == "score-resume":
        run_ats_scoring(jd_text=args.text, jd_file=args.jd)
    elif args.task == "run-custom":
        if not args.prompt:
            print("Error: --prompt is required for run-custom task.")
            sys.exit(1)
            
        print(f"\n[Orchestrator] Running custom task with Qwen: '{args.prompt}'")
        response = query_qwen(args.prompt)
        print("\n--- Qwen Response ---")
        print(response)
        print("---------------------")
        
        # Check if Qwen requests manual intervention or has a failure indicator
        if "fail" in response.lower() or "error" in response.lower() or "[trigger_antigravity]" in response:
            findings = f"""# Qwen Custom Task Execution Report

Qwen executed the prompt but encountered an issue or flagged that it needs help.

## Original Prompt:
"{args.prompt}"

## Qwen Output:
{response}
"""
            with open(FINDINGS_PATH, "w", encoding="utf-8") as f:
                f.write(findings)
                
            trigger_antigravity(
                FINDINGS_PATH,
                "Qwen executed a custom task and reported errors or flagged the need for Antigravity's assistance. Please resolve."
            )

if __name__ == "__main__":
    main()
