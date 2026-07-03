import os
import re
import json
import sqlite3
import subprocess
import urllib.request
import sys

# Dynamic Paths Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR) # Enable importing sibling modules

ROOT_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "backend" else SCRIPT_DIR
PARENT_DIR = os.path.dirname(ROOT_DIR)

WORKSPACE_DIR = os.path.dirname(PARENT_DIR) # Two levels up from ROOT_DIR (/home/chitrarth/Chitrarth)
OUTPUT_PROFILE_PATH = os.path.join(ROOT_DIR, "project_profiles.json")
RESUME_PATH = os.path.join(PARENT_DIR, "overleaf", "main.tex")
ATS_CONFIG_PATH = os.path.join(ROOT_DIR, "ats_config.json")

from validate_latex import validate_latex

OLLAMA_MODEL = "qwen2.5:14b"
CRG_PATH = "/home/chitrarth/.local/bin/code-review-graph"

EXCLUDED_DIRS = {
    "node_modules", "venv", ".git", ".next", ".expo", ".gradle", "build", 
    "temp", "test", "New folder", "SHA and JKS NEODISHA", "dist", "out"
}

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

def clean_latex(response):
    if not response:
        return ""
    if "```latex" in response:
        response = response.split("```latex")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()
    return response

def find_project_roots(base_dir):
    project_roots = []
    print(f"[Pipeline] Scanning {base_dir} for project roots...")
    for root, dirs, files in os.walk(base_dir):
        if ".git" in dirs:
            project_roots.append(root)
            dirs.clear()  # Stop walking deeper inside this repository
            continue
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
    return project_roots

def build_ast_graph(project_path):
    db_path = os.path.join(project_path, ".code-review-graph", "graph.db")
    if os.path.exists(db_path):
        return True
        
    try:
        subprocess.run(
            [CRG_PATH, "build"], 
            cwd=project_path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=40
        )
        return os.path.exists(db_path)
    except Exception:
        return False

def extract_ast_metadata(project_path):
    db_path = os.path.join(project_path, ".code-review-graph", "graph.db")
    if not os.path.exists(db_path):
        return {}
        
    metadata = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Files count
        cursor.execute("SELECT COUNT(*) FROM nodes WHERE kind = 'File';")
        metadata["file_count"] = cursor.fetchone()[0]
        
        # Languages
        cursor.execute("SELECT DISTINCT language FROM nodes WHERE language IS NOT NULL AND language != '';")
        metadata["languages"] = [r[0] for r in cursor.fetchall()]
        
        # Classes
        cursor.execute("SELECT name, qualified_name, file_path FROM nodes WHERE kind = 'Class' LIMIT 15;")
        metadata["classes"] = [{"name": r[0], "qualified": r[1], "file": r[2]} for r in cursor.fetchall()]
        
        # Key functions
        cursor.execute("SELECT name, file_path, signature FROM nodes WHERE kind = 'Function' LIMIT 15;")
        metadata["functions"] = [{"name": r[0], "file": r[1], "signature": r[2]} for r in cursor.fetchall()]
        
        # Import map
        cursor.execute("SELECT source_qualified, target_qualified FROM edges WHERE kind = 'IMPORTS_FROM' LIMIT 15;")
        metadata["imports"] = [{"source": r[0], "target": r[1]} for r in cursor.fetchall()]
        
        conn.close()
    except Exception as e:
        metadata["error"] = str(e)
        
    return metadata

def deep_analyze_project(project_path):
    project_name = os.path.basename(project_path)
    print(f"\n[Pipeline] Deep-diving into: {project_name}")
    
    # Run code-review-graph
    build_ast_graph(project_path)
    ast_info = extract_ast_metadata(project_path)
    
    if not ast_info or ast_info.get("file_count", 0) == 0:
        # Fallback summary if no AST node found
        return {
            "project_name": project_name,
            "path": project_path,
            "summary": f"Full-stack project centered on {project_name} codebase.",
            "tech_stack": ["React Native", "TypeScript", "Node.js"] if "native" in project_name.lower() else ["React.js", "Node.js"],
            "highlights": [f"Implemented core client components and server APIs in {project_name}."]
        }
        
    prompt = f"""You are an AI Software Architect. Analyze the following AST graph metadata and summarize it for a professional resume.
Strictly return a JSON object (no markdown block, no explanation) with these keys:
- "project_name": "{project_name}"
- "summary": A 2-3 sentence description of the project's purpose and functionality.
- "tech_stack": A list of the core technologies, frameworks, and languages used.
- "highlights": A list of 3-4 highly detailed, precise developer accomplishments or technical features implemented in this repository, referencing specific classes or functions from the metadata. Use technical words (e.g. NDK, WebSocket, Aggregation, on-device models).

Project Metadata:
{json.dumps(ast_info, indent=2)}
"""
    response = query_qwen(prompt, json_format=True)
    if not response:
        return None
        
    try:
        return json.loads(response)
    except Exception:
        return None

def get_git_commit_hash(project_path):
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_path, capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None

def run_pipeline():
    # Step 1: Deep analysis of all projects
    roots = find_project_roots(WORKSPACE_DIR)
    print(f"[Pipeline] Found {len(roots)} projects to analyze.")
    
    # Load cached profiles
    cached_profiles = {}
    if os.path.exists(OUTPUT_PROFILE_PATH):
        try:
            with open(OUTPUT_PROFILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for p in data:
                    if "path" in p:
                        cached_profiles[p["path"]] = p
        except Exception:
            pass
            
    profiles = []
    # For speed, we will limit Qwen queries to projects that have active code
    for r in roots:
        commit_hash = get_git_commit_hash(r)
        cached = cached_profiles.get(r)
        
        # Check if we can reuse cache
        if cached and cached.get("git_hash") == commit_hash and commit_hash is not None:
            print(f"[Pipeline] Reusing cached profile for {os.path.basename(r)} (commit {commit_hash})")
            profiles.append(cached)
        else:
            profile = deep_analyze_project(r)
            if profile:
                profile["git_hash"] = commit_hash
                profile["path"] = r
                profiles.append(profile)
            
        # Progressive save after each step to allow interruption recovery
        try:
            os.makedirs(os.path.dirname(OUTPUT_PROFILE_PATH), exist_ok=True)
            with open(OUTPUT_PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2)
        except Exception:
            pass
    print(f"\n[Pipeline] Deep project profiles cached successfully to {OUTPUT_PROFILE_PATH}!")
    
    # Step 2: Run ATS Optimization using the target/default JD
    print("\n[Pipeline] Running ATS resume tailoring on main.tex...")
    jd_content = """
    Looking for a Senior Mobile & Full Stack Engineer with strong experience in React Native, Kotlin, and JavaScript/TypeScript.
    Experience implementing secure mobile authentication, SSL certificate pinning, encryption, obfuscation, VAPT hardening, 
    and high-performance camera integration. Experience in Node.js, Express, MongoDB, Next.js, and Cloud Infrastructure (Azure).
    """
    
    # Analyze JD
    prompt_jd = f"""You are an expert ATS (Applicant Tracking System) parser. Analyze the following target job description.
Extract all key technologies, programming languages, databases, cloud infrastructure tools, security methodologies, and developer practices mentioned.
Categorize them and return a JSON object with these keys:
- "languages_frameworks": List of target languages/frameworks
- "databases_infra": List of databases and infrastructure
- "tools_practices": List of tools and practices
- "high_priority_keywords": A list of the 8 most crucial keywords the candidate must match.

Job Description:
{jd_content}
"""
    jd_response = query_qwen(prompt_jd, json_format=True)
    if not jd_response:
        print("Failed to analyze Job Description.")
        return
        
    jd_keywords = json.loads(jd_response)
    print(f"[Pipeline] Extracted Keywords: {json.dumps(jd_keywords, indent=2)}")
    
    # Merge and update LaTeX resume
    with open(RESUME_PATH, "r", encoding="utf-8") as f:
        resume_content = f.read()
        
    parts = re.split(r'(\\section\{Technical Skills\}|\\section\{Experience\}|\\section\{Projects\}|\\section\{Education\})', resume_content)
    if len(parts) < 9:
        print("Error parsing resume sections.")
        return
        
    header = parts[0]
    tech_skills_header = parts[1]
    tech_skills_content = parts[2]
    experience_header = parts[3]
    experience_content = parts[4]
    projects_header = parts[5]
    projects_content = parts[6]
    education_header = parts[7]
    education_footer = parts[8]
    
    # 1. Skills update (union)
    skills_prompt = f"""Update the Technical Skills LaTeX table. UNION/MERGE target keywords with existing ones without deleting anything.
Target: {json.dumps(jd_keywords, indent=2)}
Content:
{tech_skills_header}
{tech_skills_content}
Return ONLY updated LaTeX. No comments.
"""
    updated_skills = clean_latex(query_qwen(skills_prompt))
    
    # 2. Projects update
    projects_prompt = f"""Rewrite the Projects LaTeX section. For each project:
1. List technologies separately under a first bullet point like: \\resumeItem{{\\textbf{{Technologies Used:}} ...}}
2. Add more descriptive words and expand highlights to match the deep AST architecture details (ONNX Runtime, Metro transformer, WebSocket, SQLite, etc.) and VAPT.
3. Label projects clearly: Personal Project, Reliance Deployment, or Open Source Project.
4. Do not drop any of the 6 projects.

Original Projects:
{projects_header}
{projects_content}
Return ONLY updated LaTeX. No comments.
"""
    updated_projects = clean_latex(query_qwen(projects_prompt))
    
    # 3. Experience update
    exp_prompt = f"""Rewrite the Experience LaTeX section. Expand details for Neo Disha, NeoQCR, and Disha to include VAPT security metrics and Reliance Environments.
Original Experience:
{experience_header}
{experience_content}
Return ONLY updated LaTeX. No comments.
"""
    updated_exp = clean_latex(query_qwen(exp_prompt))
    
    if (updated_skills and "tabular" in updated_skills and 
        updated_projects and "resumeProjectHeading" in updated_projects and
        updated_exp and "resumeItemListStart" in updated_exp):
        
        final_resume = (
            header + 
            updated_skills + "\n" +
            updated_exp + "\n" +
            updated_projects + "\n" +
            education_header + education_footer
        )
        
        with open(RESUME_PATH, "w", encoding="utf-8") as f:
            f.write(final_resume)
        print("\n[Pipeline] Resume successfully optimized and saved!")
        
        # Step 3: Validate LaTeX syntax
        validate_latex(RESUME_PATH)
    else:
        print("[Pipeline] Resume tailoring failed: invalid model outputs.")

if __name__ == "__main__":
    run_pipeline()
