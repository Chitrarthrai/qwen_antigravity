import os
import json
import urllib.request
import re
import argparse

# Configuration
PROFILES_PATH = "/home/chitrarth/Chitrarth/Project P/qwen_antigravity/project_profiles.json"
RESUME_PATH = "/home/chitrarth/Chitrarth/Project P/overleaf/main.tex"
OLLAMA_MODEL = "qwen2.5:14b"
ATS_CONFIG_PATH = "/home/chitrarth/Chitrarth/Project P/qwen_antigravity/ats_config.json"

def query_qwen(prompt, json_format=False):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 4096  # Larger context for job descriptions
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

def clean_latex(response):
    if not response:
        return ""
    if "```latex" in response:
        response = response.split("```latex")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()
    return response

def load_ats_config():
    if os.path.exists(ATS_CONFIG_PATH):
        try:
            with open(ATS_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"target_roles": [], "keywords_cache": {}}

def save_ats_config(config):
    os.makedirs(os.path.dirname(ATS_CONFIG_PATH), exist_ok=True)
    with open(ATS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def analyze_job_description(jd_text):
    print("\n[ATS] Analyzing Job Description using local Qwen...")
    prompt = f"""You are an expert ATS (Applicant Tracking System) parser. Analyze the following target job description.
Extract all key technologies, programming languages, databases, cloud infrastructure tools, security methodologies, and developer practices mentioned.
Categorize them and return a JSON object with these keys:
- "languages_frameworks": List of target languages/frameworks (e.g. ["React Native", "Kotlin"])
- "databases_infra": List of databases and infrastructure (e.g. ["PostgreSQL", "Azure"])
- "tools_practices": List of tools and practices (e.g. ["VAPT", "obfuscation", "CI/CD"])
- "high_priority_keywords": A list of the 8 most crucial keywords the candidate must match to pass the ATS parser.

Job Description:
{jd_text}
"""
    response = query_qwen(prompt, json_format=True)
    if not response:
        return None
    try:
        return json.loads(response)
    except Exception as e:
        print(f"Failed to parse target keyword JSON: {e}")
        return None

def optimize_resume(jd_keywords):
    if not os.path.exists(PROFILES_PATH):
        print(f"Project profiles not found at {PROFILES_PATH}. Run analysis first.")
        return False
        
    with open(PROFILES_PATH, "r", encoding="utf-8") as f:
        profiles = json.load(f)
        
    with open(RESUME_PATH, "r", encoding="utf-8") as f:
        resume_content = f.read()
        
    # Split resume into parts
    parts = re.split(r'(\\section\{Technical Skills\}|\\section\{Experience\}|\\section\{Projects\}|\\section\{Education\})', resume_content)
    if len(parts) < 9:
        print("Error: Resume structure does not match expected sections.")
        return False
        
    header = parts[0]
    tech_skills_header = parts[1]
    tech_skills_content = parts[2]
    experience_header = parts[3]
    experience_content = parts[4]
    projects_header = parts[5]
    projects_content = parts[6]
    education_header = parts[7]
    education_footer = parts[8]
    
    # 1. Update Technical Skills to align with high priority keywords
    print("\n[ATS] Tailoring Technical Skills table...")
    skills_prompt = f"""You are an ATS optimization assistant. Update the Technical Skills LaTeX table below.
CRITICAL: Do NOT delete or drop any existing technical skills (like C++, Python, PostgreSQL, Firebase, OpenCV, OCR, Android NDK/SDK, Performance Optimization).
Instead, UNION/MERGE the target ATS keywords with the existing ones, de-duplicating them.
Keep the skills categorized correctly (Languages/Frameworks, Databases/Infra, Tools/Practices).
Do not change the LaTeX table structure, column layout, or spacing.

Target ATS Keywords:
{json.dumps(jd_keywords, indent=2)}

Original Technical Skills Content:
{tech_skills_header}
{tech_skills_content}

Return ONLY the updated LaTeX block for the Technical Skills section. No explanations.
"""
    updated_skills = query_qwen(skills_prompt)
    updated_skills_clean = clean_latex(updated_skills)
    
    # 2. Update Projects or Experience to match ATS requirements
    # Specifically highlighting the security/VAPT updates in IRM neodisha_native
    print("\n[ATS] Optimizing Experience and Projects bullet points with VAPT, Security, and other matched accomplishments...")
    
    # Find neodisha_native IRM profile details
    irm_profile = {}
    for p in profiles:
        if "neodisha_native" in p.get("project_name", "") and "/IRM/" in p.get("path", ""):
            irm_profile = p
            break
    if not irm_profile:
        # Fallback to any neodisha_native
        for p in profiles:
            if "neodisha_native" in p.get("project_name", ""):
                irm_profile = p
                break
                
    projects_prompt = f"""You are a senior developer resume optimizer. Review the projects section of the resume.
We need to update it to:
1. Emphasize the Security, VAPT (Vulnerability Assessment & Penetration Testing), Obfuscation, and 2-step auth flows implemented in the Neo Disha (Native App) in the IRM folder.
2. Incorporate target ATS keywords where appropriate while keeping all 6 projects intact in their original order:
   - FinanceTask
   - FedEx Document Processing Pipeline
   - Neo Disha (Native App)
   - Disha | Blushlace & Dashboard
   - CheckIt (Quick Commerce Price Comparison)
   - Argo CD MCP Server

IRM Security Details for Neo Disha:
- SSL Certificate Pinning, programmatic Firebase Initialization with dynamic config options to prevent hardcoded API key leakage.
- Strong ProGuard/R8 obfuscation rules and log-stripping pipelines to prevent reverse-engineering.
- 2-step auth flow using short-lived session tokens and dynamic bypass verification to prevent JWT authentication leaks.
- TurboModule architecture migration.

Target ATS Keywords:
{json.dumps(jd_keywords, indent=2)}

Original Projects Content:
{projects_header}
{projects_content}

Return ONLY the updated Projects LaTeX block. No explanation.
"""
    updated_projects = query_qwen(projects_prompt)
    updated_projects_clean = clean_latex(updated_projects)
    
    # 3. Update Experience Section (specifically Neophyte AI role to highlight Neo Disha security and other ATS matches)
    print("\n[ATS] Tailoring Experience bullets...")
    exp_prompt = f"""You are a professional resume writer. Tailor the Experience section below to highlight relevant skills.
Specifically, enhance the "Neo Disha (mobile)" and "NeoQCR" items to include:
- VAPT security audit remediations, SSL pinning configuration, and ProGuard log-stripping obfuscation.
- 2-step authentication flow refactoring to address token leakage and protect user PII.
- Keep the remaining bullets concise and fit the single-page constraints.

Target ATS Keywords:
{json.dumps(jd_keywords, indent=2)}

Original Experience Content:
{experience_header}
{experience_content}

Return ONLY the updated Experience LaTeX block. No explanation.
"""
    updated_exp = query_qwen(exp_prompt)
    updated_exp_clean = clean_latex(updated_exp)
    
    # Reassemble and save
    if (updated_skills_clean and "tabular" in updated_skills_clean and 
        updated_projects_clean and "resumeProjectHeading" in updated_projects_clean and
        updated_exp_clean and "resumeItemListStart" in updated_exp_clean):
        
        final_resume = (
            header + 
            updated_skills_clean + "\n" +
            updated_exp_clean + "\n" +
            updated_projects_clean + "\n" +
            education_header + education_footer
        )
        
        with open(RESUME_PATH, "w", encoding="utf-8") as f:
            f.write(final_resume)
        print("\n[ATS] Resume successfully optimized and saved!")
        return True
    else:
        print("\n[ATS] Failed to optimize resume: invalid or incomplete LaTeX returned from Qwen.")
        return False

def main():
    parser = argparse.ArgumentParser(description="ATS Resume Tailoring Tool using Local Qwen")
    parser.add_argument("--jd", type=str, help="Path to a text file containing the job description")
    parser.add_argument("--text", type=str, help="Raw job description text")
    args = parser.parse_args()
    
    jd_content = ""
    if args.jd:
        if os.path.exists(args.jd):
            with open(args.jd, "r", encoding="utf-8") as f:
                jd_content = f.read()
        else:
            print(f"File not found: {args.jd}")
            return
    elif args.text:
        jd_content = args.text
    else:
        # Default fallback: scan for security and mobile optimization keywords
        print("[ATS] No job description provided. Using standard Senior/Security Mobile Developer profile keywords...")
        jd_content = """
        Looking for a Senior Mobile & Full Stack Engineer with strong experience in React Native, Kotlin, and JavaScript/TypeScript.
        Experience implementing secure mobile authentication, SSL certificate pinning, encryption, obfuscation, VAPT hardening, 
        and high-performance camera integration. Experience in Node.js, Express, MongoDB, Next.js, and Cloud Infrastructure (Azure).
        """
        
    # Analyze
    jd_keywords = analyze_job_description(jd_content)
    if not jd_keywords:
        print("Could not extract keywords.")
        return
        
    print(f"\n[ATS] Extracted Target Keywords: {json.dumps(jd_keywords, indent=2)}")
    
    # Cache keywords
    config = load_ats_config()
    config["target_roles"].append({
        "timestamp": os.popen("date").read().strip(),
        "extracted_keywords": jd_keywords
    })
    save_ats_config(config)
    
    # Tailor
    success = optimize_resume(jd_keywords)
    if success:
        print("[ATS] Tailoring complete! Check main.tex.")

if __name__ == "__main__":
    main()
