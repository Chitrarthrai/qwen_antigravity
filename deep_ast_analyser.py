import os
import json
import urllib.request
import sqlite3
import subprocess

# Configuration
PROJECTS = {
    "Neo Disha (Native App)": "/home/chitrarth/Chitrarth/IRM/neodisha_native",
    "FinanceTask": "/home/chitrarth/Chitrarth/Project P/FinanceTask",
    "Argo CD MCP Server": "/home/chitrarth/Chitrarth/learn/argocd-mcp",
    "Neo QA Server": "/home/chitrarth/Chitrarth/learn/trends-beauty/backend/backend_without_excel/neo_QA/server"
}
OLLAMA_MODEL = "qwen2.5:14b"
CRG_PATH = "/home/chitrarth/.local/bin/code-review-graph"
OUTPUT_REPORT_PATH = "/home/chitrarth/Chitrarth/Project P/qwen_antigravity/deep_codebase_architecture.md"

def query_qwen(prompt):
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 4096  # Larger context to ingest code maps
        }
    }
    
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

def build_ast_db(project_path):
    db_path = os.path.join(project_path, ".code-review-graph", "graph.db")
    if os.path.exists(db_path):
        print(f"[AST] Found existing database for {os.path.basename(project_path)}.")
        return True
    
    print(f"[AST] Database not found. Building AST graph for {os.path.basename(project_path)}...")
    try:
        res = subprocess.run(
            [CRG_PATH, "build"],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60
        )
        return res.returncode == 0
    except Exception as e:
        print(f"[AST] Failed to build AST database: {e}")
        return False

def extract_ast_data(project_path):
    db_path = os.path.join(project_path, ".code-review-graph", "graph.db")
    if not os.path.exists(db_path):
        return None
        
    data = {
        "files": [],
        "classes": [],
        "functions": [],
        "imports": [],
        "calls": []
    }
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Files
        cursor.execute("SELECT qualified_name, language FROM nodes WHERE kind = 'File' LIMIT 30;")
        data["files"] = [{"name": r[0], "language": r[1]} for r in cursor.fetchall()]
        
        # Classes
        cursor.execute("SELECT name, qualified_name, file_path FROM nodes WHERE kind = 'Class' LIMIT 20;")
        data["classes"] = [{"name": r[0], "qualified": r[1], "file": r[2]} for r in cursor.fetchall()]
        
        # Functions / Methods
        cursor.execute("SELECT name, file_path, signature FROM nodes WHERE kind = 'Function' LIMIT 40;")
        data["functions"] = [{"name": r[0], "file": r[1], "signature": r[2]} for r in cursor.fetchall()]
        
        # Core imports / dependencies
        cursor.execute("""
            SELECT source_qualified, target_qualified 
            FROM edges 
            WHERE kind = 'IMPORTS_FROM' OR kind = 'DEPENDS_ON'
            LIMIT 30;
        """)
        data["imports"] = [{"source": r[0], "target": r[1]} for r in cursor.fetchall()]
        
        # Core function calls
        cursor.execute("""
            SELECT source_qualified, target_qualified 
            FROM edges 
            WHERE kind = 'CALLS'
            LIMIT 30;
        """)
        data["calls"] = [{"source": r[0], "target": r[1]} for r in cursor.fetchall()]
        
        conn.close()
    except Exception as e:
        print(f"[AST] Error reading database: {e}")
        
    return data

def main():
    report_markdown = """# Deep Codebase Architecture & AST Flow Report

This report presents a deep-dive structural analysis of key projects in the workspace. The architecture schemas, classes, functions, and import/call maps were extracted directly from local AST databases built using the `code-review-graph` plugin, and analyzed with the local `qwen2.5:14b` model.

---
"""
    
    for name, path in PROJECTS.items():
        print(f"\n==========================================")
        print(f"Deep Analyzing project: {name}")
        print(f"Path: {path}")
        print(f"==========================================")
        
        if not os.path.exists(path):
            print(f"Path does not exist: {path}. Skipping.")
            continue
            
        success = build_ast_db(path)
        if not success:
            print(f"Could not build/locate AST database. Skipping.")
            continue
            
        ast_data = extract_ast_data(path)
        if not ast_data:
            print(f"No AST data extracted. Skipping.")
            continue
            
        print(f"[AST] Extracted data. Querying Qwen for architecture analysis...")
        prompt = f"""You are a Principal Software Architect. Analyze the following AST graph metadata (files, classes, functions, calls, and imports) for the project "{name}".
Provide a highly technical, deep-dive architectural analysis of this codebase. Organize your output into the following markdown sections:
1. **Core Architectural Pattern**: (e.g. Clean Architecture, MVC, client-server, etc., based on folders, imports, and classes)
2. **Primary Code Flow / Execution Path**: Explain the sequence of operations from the entry point down to core services, referencing specific function names and call maps.
3. **Key Components & Utilities**: Describe the roles of the main classes and functions, explaining how they interact.
4. **Dependencies & Frameworks**: Outline the import structures and explain which packages are utilized.

AST Data:
{json.dumps(ast_data, indent=2)}

Do not include introductions or high-level explanations. Start directly with the markdown headers.
"""
        qwen_analysis = query_qwen(prompt)
        if not qwen_analysis:
            print(f"Failed to get analysis from Qwen.")
            continue
            
        report_markdown += f"\n## 📁 Project: {name}\n"
        report_markdown += f"- **Path**: `{path}`\n\n"
        report_markdown += qwen_analysis
        report_markdown += "\n\n---\n"
        
    # Write final report
    os.makedirs(os.path.dirname(OUTPUT_REPORT_PATH), exist_ok=True)
    with open(OUTPUT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_markdown)
        
    print(f"\n[Deep Analysis] Completed! Report saved to {OUTPUT_REPORT_PATH}")

if __name__ == "__main__":
    main()
