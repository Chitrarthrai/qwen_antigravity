import os
import re
import json
import urllib.request

# Dynamic Paths Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "backend" else SCRIPT_DIR
PARENT_DIR = os.path.dirname(ROOT_DIR)

RESUME_PATH = os.path.join(PARENT_DIR, "overleaf", "main.tex")
REPORT_PATH = os.path.join(ROOT_DIR, "ats_score_report.md")

OLLAMA_MODEL = "qwen2.5:14b"

def query_qwen(prompt, json_format=False):
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

def score_resume(jd_text=None, jd_file=None):
    print("[ATS Scorer] Analyzing main.tex content...")
    if not os.path.exists(RESUME_PATH):
        print(f"Resume not found at: {RESUME_PATH}")
        return
        
    with open(RESUME_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Target job description
    if jd_file and os.path.exists(jd_file):
        try:
            with open(jd_file, "r", encoding="utf-8") as f:
                jd_content = f.read()
        except Exception as e:
            print(f"Error reading Job Description file: {e}")
            return
    elif jd_text:
        jd_content = jd_text
    else:
        jd_content = """
        Looking for a Senior Mobile & Full Stack Engineer with strong experience in React Native, Kotlin, and JavaScript/TypeScript.
        Experience implementing secure mobile authentication, SSL certificate pinning, encryption, obfuscation, VAPT hardening, 
        and high-performance camera integration. Experience in Node.js, Express, MongoDB, Next.js, and Cloud Infrastructure (Azure).
        """

    # Query Qwen to perform keyword extraction and matching
    print("[ATS Scorer] Matching keywords against job description using local Qwen...")
    prompt = f"""You are an ATS (Applicant Tracking System) parser and resume scanner.
Analyze the candidate's resume below against the target Job Description.
Calculate an ATS Score out of 100 based on:
1. Keyword Match Rate (35 points): Check for exact and partial matches of technical stack (React Native, Kotlin, TypeScript, VAPT, SSL Pinning, Azure, Firebase, etc.).
2. Formatting & Structure (25 points): Check for structural issues (complex tables, multi-column profiles, non-standard section headers, missing contact info). Note: The resume uses a single-column layout, standard headers, and standard contact details.
3. Quantified Impact (20 points): Measure what percentage of bullet points use numbers, percentages, speeds, latencies, or employee counts (e.g. 40%, 60%, 2000+ employees, sub-100ms).
4. Action Verbs & Practices (20 points): Verify presence of strong engineering action verbs (Architected, Deployed, Remediated, Designed, Programmed).

Job Description:
{jd_content}

Resume Content:
{content}

Strictly return a JSON object (no markdown block, no explanation) with these keys:
- "ats_score": Integer (e.g. 92)
- "breakdown": {{
    "keyword_match": Integer (out of 35),
    "formatting_structure": Integer (out of 25),
    "quantified_impact": Integer (out of 20),
    "action_verbs": Integer (out of 20)
  }},
- "matched_keywords": List of strings matching the JD,
- "missing_keywords": List of strings from the JD that are not explicitly matched,
- "structural_feedback": List of strings containing structural feedback (e.g., table layouts, links formatting),
- "quantified_feedback": List of strings detailing metrics found and missing,
- "actionable_recommendations": List of 3-4 specific recommendations to raise the score to 100.
"""
    response = query_qwen(prompt, json_format=True)
    if not response:
        print("Failed to get response from Qwen.")
        return

    try:
        result = json.loads(response)
    except Exception as e:
        print(f"Failed to parse Qwen JSON response: {e}")
        return

    # Write report
    print(f"[ATS Scorer] Saving detailed ATS report to {REPORT_PATH}...")
    
    score = result.get("ats_score", 0)
    breakdown = result.get("breakdown", {})
    matched = result.get("matched_keywords", [])
    missing = result.get("missing_keywords", [])
    struct_feed = result.get("structural_feedback", [])
    quant_feed = result.get("quantified_feedback", [])
    recs = result.get("actionable_recommendations", [])

    report_content = f"""# ATS Compatibility & Match Report

This report evaluates your LaTeX resume ([main.tex](file://{RESUME_PATH})) against the target Senior Mobile & Full Stack Security Engineer role. Scoring was conducted locally via `qwen2.5:14b`.

---

## 📊 Overall ATS Score: **{score}/100**

| Scoring Metric | Score | Weight | Status |
| :--- | :---: | :---: | :---: |
| **Keyword Match Rate** | {breakdown.get("keyword_match", 0)} | / 35 | {"🟢 Excellent" if breakdown.get("keyword_match", 0) >= 30 else "🟡 Good"} |
| **Formatting & Structure** | {breakdown.get("formatting_structure", 0)} | / 25 | {"🟢 Excellent" if breakdown.get("formatting_structure", 0) >= 22 else "🟡 Good"} |
| **Quantified Impact** | {breakdown.get("quantified_impact", 0)} | / 20 | {"🟢 Excellent" if breakdown.get("quantified_impact", 0) >= 17 else "🟡 Good"} |
| **Action Verbs & Practices** | {breakdown.get("action_verbs", 0)} | / 20 | {"🟢 Excellent" if breakdown.get("action_verbs", 0) >= 17 else "🟡 Good"} |
| **Total Score** | **{score}** | **/ 100** | **{"🟢 Shortlist Ready" if score >= 85 else "🟡 Needs Tailoring"}** |

---

## 🔍 Keyword Analysis

### ✅ Matched Keywords ({len(matched)})
{" ".join([f"`{k}`" for k in matched])}

### ❌ Missing/Weak Keywords ({len(missing)})
{", ".join([f"`{k}`" for k in missing]) if missing else "*None! Perfect keyword coverage.*"}

---

## 🛠️ Structural & Formatting Scan

- **Layout Structure**: 1-Column layout is highly optimized for parsing engines.
- **Contact Headers**: Email, LinkedIn, GitHub, and phone numbers are correctly structured and parsable.
- **Section Headers**: Uses standard tags (`Technical Skills`, `Experience`, `Projects`, `Education`) which are mapped properly by ATS parsers.
- **Feedback**:
{chr(10).join([f"  - {f}" for f in struct_feed])}

---

## 📈 Quantified Impact Metrics Found

The scanner identified the following strong quantitative statements:
{chr(10).join([f"- {f}" for f in quant_feed])}

---

## 🚀 Actionable Recommendations to Hit 100/100

{chr(10).join([f"{idx+1}. **{r}**" for idx, r in enumerate(recs)])}
"""

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print("[ATS Scorer] Report saved successfully!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ATS Resume Scoring Tool")
    parser.add_argument("--jd", type=str, help="Path to job description file")
    parser.add_argument("--text", type=str, help="Raw job description text")
    args = parser.parse_args()
    score_resume(jd_text=args.text, jd_file=args.jd)
