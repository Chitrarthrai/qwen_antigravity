#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import json
import urllib.request
import re
import fnmatch
import time
import sqlite3
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configurations
OLLAMA_MODEL = "qwen2.5:14b"
CRG_PATH = "/home/chitrarth/.local/bin/code-review-graph"
ANTIGRAVITY_PATH = "/usr/bin/antigravity"
_script_dir = os.path.dirname(os.path.abspath(__file__))
ORCHESTRATOR_DIR = os.path.dirname(_script_dir) if os.path.basename(_script_dir) == "backend" else _script_dir

DEFAULT_EXCLUDES = {
    "node_modules", "venv", ".git", ".next", ".expo", ".gradle", "build", 
    "dist", "out", "temp", "test", "target", "__pycache__", "eggs", "*.egg-info"
}

def query_qwen(prompt, json_format=False):
    """Query the local Qwen model using Ollama API."""
    print(f"\n=================== [OLLAMA PROMPT SENT] ===================")
    print(prompt)
    print("============================================================\n")
    
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
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = response.read().decode('utf-8')
            res_json = json.loads(res_data)
            res_text = res_json.get("response", "").strip()
            print(f"\n=================== [OLLAMA RESPONSE RECEIVED] ===================")
            print(res_text)
            print("==================================================================\n")
            return res_text
    except Exception as e:
        print(f"[Ollama] Error querying Qwen: {e}")
        return None

class GitIgnoreParser:
    """A helper class to parse and match .gitignore files dynamically."""
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.patterns = []
        
    def load_gitignore(self, dir_path):
        gitignore_file = os.path.join(dir_path, ".gitignore")
        if os.path.exists(gitignore_file):
            try:
                with open(gitignore_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Normalize path separators
                            line = line.replace("\\", "/")
                            # Keep track of directory-only matching
                            is_dir_only = line.endswith("/")
                            clean_pattern = line.rstrip("/")
                            
                            # Convert relative paths to base dir patterns
                            rel_base = os.path.relpath(dir_path, self.root_dir)
                            if rel_base == ".":
                                rel_base = ""
                            
                            self.patterns.append({
                                "pattern": clean_pattern,
                                "rel_base": rel_base,
                                "is_dir_only": is_dir_only,
                                "dir_path": os.path.abspath(dir_path)
                            })
            except Exception as e:
                print(f"[Scanner] Error reading gitignore in {dir_path}: {e}")

    def is_ignored(self, full_path, is_dir=False):
        # Always check against default excludes first
        name = os.path.basename(full_path)
        if name in DEFAULT_EXCLUDES:
            return True
        for pattern in DEFAULT_EXCLUDES:
            if fnmatch.fnmatch(name, pattern):
                return True
                
        full_path_abs = os.path.abspath(full_path)
        rel_path = os.path.relpath(full_path, self.root_dir).replace("\\", "/")
        
        for p in self.patterns:
            pattern_dir = p.get("dir_path")
            if pattern_dir:
                try:
                    rel_to_pattern_dir = os.path.relpath(full_path_abs, pattern_dir)
                    if rel_to_pattern_dir.startswith(".."):
                        continue
                except ValueError:
                    continue

            pattern = p["pattern"]
            base = p["rel_base"]
            is_dir_only = p["is_dir_only"]
            
            if is_dir_only and not is_dir:
                continue
                
            # If the gitignore was defined in a subdirectory, match relative to that directory
            if base:
                match_target = os.path.relpath(full_path, os.path.join(self.root_dir, base)).replace("\\", "/")
            else:
                match_target = rel_path
                
            # Direct match or match inside directory wildcard
            if fnmatch.fnmatch(match_target, pattern) or \
               fnmatch.fnmatch(os.path.basename(full_path), pattern) or \
               match_target.startswith(pattern + "/"):
                return True
        return False

PROJECT_SIGNATURES = [
    "package.json", "requirements.txt", "pyproject.toml", "vite.config.js", 
    "vite.config.ts", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "Gemfile"
]

def is_project_root_dir(path):
    """Check if a directory matches project root signature or contains .git."""
    try:
        files = os.listdir(path)
        if ".git" in files:
            return True
        if any(sig in files for sig in PROJECT_SIGNATURES):
            return True
    except Exception:
        pass
    return False

def has_source_files_direct(dir_path):
    """Check if there are any source files directly in this directory."""
    try:
        for entry in os.scandir(dir_path):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower()
                if ext in [".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".cpp", ".c", ".h", ".java", ".kt", ".swift", ".cs"]:
                    return True
    except Exception:
        pass
    return False

def has_independent_source_files_dynamic(dir_path, ignore_parser):
    """Check recursively if there are any source files in dir_path that do not belong to nested project roots."""
    if has_source_files_direct(dir_path):
        return True
        
    try:
        for entry in os.scandir(dir_path):
            if entry.is_dir():
                sub_path = entry.path
                if not ignore_parser.is_ignored(sub_path, is_dir=True):
                    if not is_project_root_dir(sub_path):
                        if has_independent_source_files_dynamic(sub_path, ignore_parser):
                            return True
    except Exception:
        pass
    return False

def has_nested_project_roots(dir_path, ignore_parser):
    """Check dynamically if there are any project roots nested inside dir_path."""
    try:
        for root, dirs, files in os.walk(dir_path, topdown=True):
            ignore_parser.load_gitignore(root)
            
            filtered = []
            for d in dirs:
                sub_path = os.path.join(root, d)
                if not ignore_parser.is_ignored(sub_path, is_dir=True):
                    filtered.append(d)
            dirs[:] = filtered
            
            if os.path.abspath(root) != os.path.abspath(dir_path):
                if is_project_root_dir(root):
                    return True
    except Exception:
        pass
    return False

def is_actual_project_root(path, ignore_parser, base_dir=None):
    """Determine if a path is a valid project root, avoiding base container ambiguity."""
    if not is_project_root_dir(path):
        return False
    if base_dir and os.path.abspath(path) == os.path.abspath(base_dir):
        if has_nested_project_roots(path, ignore_parser):
            return False
    return True

def find_project_roots(base_dir, ignore_parser):
    """Walk directories to find project roots dynamically, respecting boundaries."""
    project_roots = []
    print(f"[Scanner] Crawling {base_dir} to identify project folders...")
    
    for root, dirs, files in os.walk(base_dir, topdown=True):
        # Load gitignore at this level
        ignore_parser.load_gitignore(root)
        
        # Dynamically modify dirs in-place to avoid entering ignored boundaries
        filtered_dirs = []
        for d in dirs:
            dir_full_path = os.path.join(root, d)
            if not ignore_parser.is_ignored(dir_full_path, is_dir=True):
                filtered_dirs.append(d)
        dirs[:] = filtered_dirs
        
        if is_actual_project_root(root, ignore_parser, base_dir=base_dir):
            project_roots.append(root)
            dirs.clear()
            
    return project_roots

def generate_dirs_file(dirs_file, base_dir, ignore_parser):
    """Walk base_dir and write all non-ignored directories to dirs_file."""
    print(f"[Scanner] Auto-generating directory list file at {dirs_file}...")
    dir_paths = []
    
    for root, dirs, files in os.walk(base_dir, topdown=True):
        ignore_parser.load_gitignore(root)
        
        filtered = []
        for d in dirs:
            full_path = os.path.join(root, d)
            if not ignore_parser.is_ignored(full_path, is_dir=True):
                filtered.append(d)
        dirs[:] = filtered
        
        rel_path = os.path.relpath(root, base_dir)
        if rel_path == ".":
            dir_paths.append(".")
        else:
            dir_paths.append("./" + rel_path.replace(os.sep, "/"))
            
    try:
        parent_dir = os.path.dirname(dirs_file)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            
        with open(dirs_file, "w", encoding="utf-8") as f:
            for dp in dir_paths:
                f.write(dp + "\n")
        print(f"[Scanner] Successfully generated directory list with {len(dir_paths)} directories.")
    except Exception as e:
        print(f"[Scanner] Error generating dirs file {dirs_file}: {e}")

def find_project_roots_from_file(dirs_file, base_dir, ignore_parser):
    """Find project roots by reading a list of directory paths from a file."""
    project_roots = []
    print(f"[Scanner] Reading directory list from {dirs_file}...")
    
    try:
        with open(dirs_file, "r", encoding="utf-8") as f:
            paths = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"[Scanner] Error reading dirs file {dirs_file}: {e}")
        return []
        
    # Resolve all paths relative to base_dir and convert to absolute paths
    abs_paths = []
    for p in paths:
        if p.startswith("./") or p.startswith(".\\"):
            p = p[2:]
        elif p == ".":
            p = ""
        abs_path = os.path.abspath(os.path.join(base_dir, p))
        abs_paths.append(abs_path)
        
    # Sort paths by length so parents are processed before children
    abs_paths.sort(key=len)
    
    # Load gitignores hierarchically up to base_dir for each path, caching already loaded dirs
    loaded_dirs = set()
    for path in abs_paths:
        curr = path
        parents_to_load = []
        while len(curr) >= len(base_dir):
            if curr not in loaded_dirs:
                parents_to_load.append(curr)
            parent = os.path.dirname(curr)
            if parent == curr:
                break
            curr = parent
        # Load from base down to current dir
        for p_dir in reversed(parents_to_load):
            ignore_parser.load_gitignore(p_dir)
            loaded_dirs.add(p_dir)
            
    # Identify project roots and prune nested project roots efficiently using a set
    pruned_dirs = set()
    project_roots_set = set()
    for path in abs_paths:
        parent = os.path.dirname(path)
        # If parent is a project root, or parent is itself pruned, prune this child
        if parent in project_roots_set or parent in pruned_dirs:
            pruned_dirs.add(path)
            continue
            
        if ignore_parser.is_ignored(path, is_dir=True):
            pruned_dirs.add(path)
            continue
            
        if is_actual_project_root(path, ignore_parser, base_dir=base_dir):
            project_roots.append(path)
            project_roots_set.add(path)
            
    return project_roots



def classify_project(project_path):
    """Detect the tech stack details of a project path."""
    has_package = os.path.exists(os.path.join(project_path, "package.json"))
    has_requirements = os.path.exists(os.path.join(project_path, "requirements.txt"))
    has_pyproject = os.path.exists(os.path.join(project_path, "pyproject.toml"))
    has_vite = any(os.path.exists(os.path.join(project_path, f)) for f in ["vite.config.js", "vite.config.ts"])
    has_manage_py = os.path.exists(os.path.join(project_path, "manage.py"))
    has_go_mod = os.path.exists(os.path.join(project_path, "go.mod"))
    has_cargo = os.path.exists(os.path.join(project_path, "Cargo.toml"))
    has_pom = os.path.exists(os.path.join(project_path, "pom.xml"))
    has_gradle = os.path.exists(os.path.join(project_path, "build.gradle"))
    
    project_types = []
    
    if has_package:
        try:
            with open(os.path.join(project_path, "package.json"), "r", encoding="utf-8") as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "react-native" in deps:
                    project_types.append("React Native")
                elif "react" in deps:
                    project_types.append("React")
                else:
                    project_types.append("Node.js")
        except Exception:
            project_types.append("Node.js")
            
    if has_vite:
        project_types.append("Vite")
        
    if has_requirements or has_pyproject or has_manage_py or any(f.endswith(".py") for f in os.listdir(project_path) if os.path.isfile(os.path.join(project_path, f))):
        project_types.append("Python")
        
    if has_go_mod:
        project_types.append("Go")
        
    if has_cargo:
        project_types.append("Rust")
        
    if has_pom or has_gradle:
        project_types.append("Java/Kotlin")
        
    if not project_types:
        return "Unknown"
    return " & ".join(project_types)

def get_git_info(project_path):
    """Gets current git branch and list of active changes."""
    info = {"branch": "N/A", "changed_files": []}
    try:
        # Branch
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_path, capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            info["branch"] = res.stdout.strip()
            
        # Changed files
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_path, capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if len(line) > 3:
                    info["changed_files"].append(line[3:].strip())
    except Exception:
        pass
    return info

def extract_project_dependencies(project_path):
    """Extracts project dependencies from files like package.json, requirements.txt, etc."""
    dependencies = {}
    
    # Node/JS/TS
    pkg_path = os.path.join(project_path, "package.json")
    if os.path.exists(pkg_path):
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                dependencies["npm_dependencies"] = data.get("dependencies", {})
                dependencies["npm_devDependencies"] = data.get("devDependencies", {})
        except Exception:
            pass
            
    # Python requirements.txt
    req_path = os.path.join(project_path, "requirements.txt")
    if os.path.exists(req_path):
        try:
            with open(req_path, "r", encoding="utf-8") as f:
                dependencies["python_requirements"] = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        except Exception:
            pass
            
    # Python pyproject.toml
    pyproj_path = os.path.join(project_path, "pyproject.toml")
    if os.path.exists(pyproj_path):
        try:
            with open(pyproj_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                deps = []
                in_deps = False
                for line in lines:
                    line = line.strip()
                    if line.startswith("[") and "dependencies" in line:
                        in_deps = True
                        continue
                    if line.startswith("[") and not "dependencies" in line:
                        in_deps = False
                    if in_deps and line and not line.startswith("#"):
                        deps.append(line)
                if deps:
                    dependencies["python_pyproject_dependencies"] = deps
        except Exception:
            pass
            
    # Go go.mod
    go_mod_path = os.path.join(project_path, "go.mod")
    if os.path.exists(go_mod_path):
        try:
            with open(go_mod_path, "r", encoding="utf-8") as f:
                deps = []
                in_require = False
                for line in f:
                    line = line.strip()
                    if line.startswith("require ("):
                        in_require = True
                        continue
                    if line.startswith(")") and in_require:
                        in_require = False
                    if line.startswith("require") and not line.startswith("require ("):
                        deps.append(line.replace("require", "").strip())
                    elif in_require and line:
                        deps.append(line)
                if deps:
                    dependencies["go_dependencies"] = deps
        except Exception:
            pass

    return dependencies

def build_ast_db(project_path, force=False):
    """Builds the AST database for code-review-graph inside the project root."""
    db_path = os.path.join(project_path, ".code-review-graph", "graph.db")
    if os.path.exists(db_path) and not force:
        print(f"[AST] Found existing database for {os.path.basename(project_path)}.")
        return True
        
    print(f"[AST] Generating/Updating AST database for {os.path.basename(project_path)}...")
    if not os.path.exists(CRG_PATH):
        print(f"[AST] Warning: code-review-graph not found at {CRG_PATH}")
        return False
        
    try:
        if force and os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass
        res = subprocess.run(
            [CRG_PATH, "build"],
            cwd=project_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60
        )
        return res.returncode == 0 and os.path.exists(db_path)
    except Exception as e:
        print(f"[AST] Failed to build AST database: {e}")
        return False

def verify_entity_exists(db_path, entity_name, file_path):
    """Verify in the SQLite database if the entity exists in the specified file."""
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        normalized_file = file_path.replace("\\", "/")
        cursor.execute("""
            SELECT COUNT(*) FROM nodes 
            WHERE name = ? AND (
                file_path = ? OR 
                file_path LIKE ? OR 
                qualified_name LIKE ?
            );
        """, (entity_name, normalized_file, f"%/{normalized_file}", f"%{entity_name}%"))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        print(f"[Verifier] SQLite Verification Error: {e}")
        return False

def extract_ast_metadata(project_path):
    """Extracts files, classes, and function definitions from code-review-graph SQLite database."""
    db_path = os.path.join(project_path, ".code-review-graph", "graph.db")
    if not os.path.exists(db_path):
        return {}
        
    metadata = {"files": [], "classes": [], "functions": []}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Files
        cursor.execute("SELECT qualified_name, language FROM nodes WHERE kind = 'File' LIMIT 40;")
        metadata["files"] = [{"name": r[0], "language": r[1]} for r in cursor.fetchall()]
        
        # Classes
        cursor.execute("SELECT name, qualified_name, file_path FROM nodes WHERE kind = 'Class' LIMIT 30;")
        metadata["classes"] = [{"name": r[0], "qualified": r[1], "file": r[2]} for r in cursor.fetchall()]
        
        # Functions / Methods
        cursor.execute("SELECT name, file_path, signature FROM nodes WHERE kind = 'Function' LIMIT 40;")
        metadata["functions"] = [{"name": r[0], "file": r[1], "signature": r[2]} for r in cursor.fetchall()]
        
        conn.close()
    except Exception as e:
        print(f"[AST] SQLite Read Error: {e}")
        
    return metadata

def get_modified_files_content(project_path, changed_files):
    """Reads content of changed files, ignoring binaries and very large files."""
    contents = {}
    for filename in changed_files[:5]: # Limit to first 5 modified files to conserve context window
        filepath = os.path.join(project_path, filename)
        if os.path.exists(filepath) and os.path.isfile(filepath):
            # Check size < 15KB
            if os.path.getsize(filepath) < 15000:
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        contents[filename] = f.read()
                except Exception:
                    pass
    return contents

def filter_hallucinations(project_path, findings, db_path):
    """Verifies that the file paths and entities reported by Qwen actually exist."""
    verified_findings = []
    
    for finding in findings:
        file_path = finding.get("file_path", "")
        entity_name = finding.get("entity_name", "")
        
        full_file_path = os.path.join(project_path, file_path)
        if not os.path.exists(full_file_path) or not os.path.isfile(full_file_path):
            print(f"[Verifier] ⚠️ Discarded hallucination: File '{file_path}' does not exist.")
            continue
            
        # Check if entity is valid in AST or file contents
        if entity_name:
            # Check SQL database first
            if os.path.exists(db_path):
                if verify_entity_exists(db_path, entity_name, file_path):
                    verified_findings.append(finding)
                    continue
                
            # Fallback: check if the string exists in the file contents
            try:
                with open(full_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if entity_name in content:
                        verified_findings.append(finding)
                    else:
                        print(f"[Verifier] ⚠️ Discarded hallucination: Entity '{entity_name}' not found in file '{file_path}'.")
            except Exception:
                print(f"[Verifier] ⚠️ Failed reading '{file_path}' to verify entity.")
        else:
            # File exists, no entity constraint
            verified_findings.append(finding)
            
    return verified_findings

def trigger_antigravity(findings_file, project_name):
    """Triggers the Antigravity chat session in agent mode to automatically fix the findings."""
    print(f"\n[Master] 🚀 Launching Antigravity CLI to resolve findings for '{project_name}'...")
    
    prompt = (
        f"Review the code findings report in the attached findings file, search the web or "
        f"verify system documentations if necessary, and completely resolve all the bugs, code quality issues, "
        f"and security warnings reported for project {project_name}."
    )
    
    cmd = [
        ANTIGRAVITY_PATH, "chat",
        "-m", "agent",
        "-a", findings_file,
        prompt
    ]
    try:
        # Run asynchronously to allow the script to continue or check other projects
        subprocess.Popen(cmd)
        print("[Master] Antigravity chat trigger command executed successfully.")
    except Exception as e:
        print(f"[Master] Error invoking Antigravity CLI: {e}")

def get_project_file_prefix(project_path, base_path):
    """Generate a structured, unique prefix to order and differentiate nested project files."""
    if not base_path:
        return os.path.basename(project_path)
    base_abs = os.path.abspath(base_path)
    proj_abs = os.path.abspath(project_path)
    base_name = os.path.basename(base_abs)
    
    if proj_abs == base_abs:
        return base_name
        
    rel_path = os.path.relpath(proj_abs, base_abs)
    clean_rel = rel_path.replace(os.sep, "_")
    return f"{base_name}_{clean_rel}"

def run_project_review(project_path, ignore_parser, mode="analyze", base_path=None, force_ast_rebuild=False):
    """Executes the complete review sequence for a single project directory."""
    project_name = os.path.basename(project_path)
    file_prefix = get_project_file_prefix(project_path, base_path)
    project_type = classify_project(project_path)
    git_info = get_git_info(project_path)
    
    print(f"\n=== Analyzing Project: {project_name} ({mode.upper()} mode) ===")
    print(f"Path: {project_path}")
    print(f"Type: {project_type}")
    print(f"Git Branch: {git_info['branch']}")
    print(f"Active Changes: {len(git_info['changed_files'])} files modified")
    
    # 1. Update/Build AST
    should_force = force_ast_rebuild or len(git_info.get("changed_files", [])) > 0
    ast_built = build_ast_db(project_path, force=should_force)
    ast_metadata = {}
    if ast_built:
        ast_metadata = extract_ast_metadata(project_path)
        
    if mode == "analyze":
        dependencies = extract_project_dependencies(project_path)
        print("[Reviewer] Querying Qwen (slave) for codebase analysis...")
        prompt = f"""You are a Principal Software Architect.
Provide a highly detailed, professional Technical Specification & Codebase Analysis for the project "{project_name}".
 
Project Path: {project_path}
Project Type: {project_type}
Current Git Branch: {git_info['branch']}
 
External Dependencies & Modules Used:
{json.dumps(dependencies, indent=2)}
 
AST Structure Summary (files, classes, functions):
{json.dumps(ast_metadata, indent=2)}
 
Please generate a comprehensive technical report in Markdown format containing:
1. **Executive Summary**: High-level explanation of the project's purpose and functionality.
2. **Tech Stack & Core Specifications**: A detailed list/table of the languages, frameworks, and libraries detected.
3. **Modules & Dependencies**: Analysis of the main third-party dependencies used and their purpose in the application.
4. **Codebase Architecture & File Structure**: Breakdown of files, layout, and how components interact.
5. **Key Entities & Interfaces**: Detailed descriptions of the main classes, functions, and files found in the AST, explaining their roles.
6. **Data Flow & Logic Flow**: How data flows through the application (e.g., API endpoints, database interactions, frontend-backend communication).
7. **Architectural Recommendations**: Future optimizations, performance enhancements, and structure suggestions.
 
Do not output any introductory or concluding chat remarks. Output ONLY the raw Markdown content.
"""
        response = query_qwen(prompt, json_format=False)
        if not response:
            print("[Reviewer] Failed to retrieve response from Qwen.")
            return False
            
        # Log Qwen interaction
        log_path = os.path.join(ORCHESTRATOR_DIR, f"{file_prefix}_interaction.log")
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("=== PROMPT SENT TO QWEN ===\n")
                f.write(prompt)
                f.write("\n\n=== RESPONSE RECEIVED FROM QWEN ===\n")
                f.write(response)
            print(f"[Reviewer] Logged Qwen interaction to {log_path}")
        except Exception as e:
            print(f"[Reviewer] Error writing interaction log: {e}")
            
        analysis_path = os.path.join(ORCHESTRATOR_DIR, f"{file_prefix}_analysis.md")
        print(f"[Reviewer] Writing project analysis to {analysis_path}...")
        try:
            with open(analysis_path, "w", encoding="utf-8") as f:
                f.write(response)
            print("[Reviewer] ✅ Project analysis written successfully.")
            return True
        except Exception as e:
            print(f"[Reviewer] Error writing analysis file: {e}")
            return False
 
    # 2. Get modified file contents
    modified_contents = get_modified_files_content(project_path, git_info["changed_files"])
    
    # 3. Construct LLM Prompt
    prompt = f"""You are a Principal Software Engineer & Code Reviewer.
Analyze the codebase information for the project "{project_name}" and identify bugs, security vulnerabilities, syntax issues, or code quality improvements.
 
Project Type: {project_type}
Current Git Branch: {git_info['branch']}
Modified/Untracked Files: {json.dumps(git_info['changed_files'])}
 
AST Structure Summary (files, classes, functions):
{json.dumps(ast_metadata, indent=2)}
 
File Contents of Modified Files:
"""
    for file, content in modified_contents.items():
        prompt += f"\n--- File: {file} ---\n{content}\n"
        
    prompt += """
Strictly return a JSON object containing a list of findings. Do not output any introduction, explanation, or markdown syntax.
JSON Schema format:
{
  "findings": [
    {
      "file_path": "path/to/file.py",
      "entity_name": "function_or_class_name",
      "issue_type": "bug | security | code_quality | performance",
      "severity": "critical | major | minor",
      "issue_description": "Clear explanation of the bug or issue.",
      "suggested_fix": "Detailed instructions on how to rewrite or fix this code."
    }
  ]
}
If no issues are found, return:
{
  "findings": []
}
"""
 
    print("[Reviewer] Querying Qwen (slave) for code review...")
    response = query_qwen(prompt, json_format=True)
    if not response:
        print("[Reviewer] Failed to retrieve response from Qwen.")
        return False
        
    # Log Qwen interaction
    log_path = os.path.join(ORCHESTRATOR_DIR, f"{file_prefix}_interaction.log")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=== PROMPT SENT TO QWEN ===\n")
            f.write(prompt)
            f.write("\n\n=== RESPONSE RECEIVED FROM QWEN ===\n")
            f.write(response)
        print(f"[Reviewer] Logged Qwen interaction to {log_path}")
    except Exception as e:
        print(f"[Reviewer] Error writing interaction log: {e}")
        
    try:
        res_json = json.loads(response)
        findings = res_json.get("findings", [])
    except Exception as e:
        print(f"[Reviewer] Error parsing Qwen JSON response: {e}")
        # Clean up any potential markdown wraps and retry parsing
        clean_response = response.replace("```json", "").replace("```", "").strip()
        try:
            res_json = json.loads(clean_response)
            findings = res_json.get("findings", [])
        except Exception:
            print("[Reviewer] Retrying JSON parsing failed.")
            return False
            
    if not findings:
        print("[Reviewer] ✅ No issues found by local Qwen.")
        return True
        
    print(f"[Reviewer] Qwen reported {len(findings)} issues. Performing anti-hallucination verification...")
    db_path = os.path.join(project_path, ".code-review-graph", "graph.db")
    verified = filter_hallucinations(project_path, findings, db_path)
    print(f"[Reviewer] Verified {len(verified)} / {len(findings)} findings.")
    
    if not verified:
        print("[Reviewer] ✅ All reported issues were discarded as LLM hallucinations.")
        return True
        
    # Write findings report
    findings_path = os.path.join(ORCHESTRATOR_DIR, f"{file_prefix}_review_findings.md")
    print(f"[Reviewer] Writing findings to {findings_path}...")
    
    report_content = f"# Qwen Code Review Findings for {project_name}\n"
    report_content += f"- **Target Path**: `{project_path}`\n"
    report_content += f"- **Project Type**: {project_type}\n"
    report_content += f"- **Branch**: `{git_info['branch']}`\n"
    report_content += f"- **Review Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report_content += "## Identified Issues\n\n"
    
    for idx, f in enumerate(verified):
        report_content += f"### {idx+1}. {f['issue_type'].upper()}: {f['severity'].upper()} severity in `{f['file_path']}`\n"
        if f.get('entity_name'):
            report_content += f"- **Entity**: `{f['entity_name']}`\n"
        report_content += f"- **Description**: {f['issue_description']}\n"
        report_content += f"- **Suggested Fix**:\n```\n{f['suggested_fix']}\n```\n\n"
        
    try:
        with open(findings_path, "w", encoding="utf-8") as rep_file:
            rep_file.write(report_content)
    except Exception as e:
        print(f"[Reviewer] Error writing findings file: {e}")
        return False
        
    # Trigger Antigravity Auto-Fix
    trigger_antigravity(findings_path, project_name)
    return True

def find_parent_project_root(filepath, base_path, ignore_parser=None):
    """Walk up parent directories of a modified file to find its project root."""
    current = os.path.dirname(os.path.abspath(filepath))
    base_abs = os.path.abspath(base_path)
    if ignore_parser is None:
        ignore_parser = GitIgnoreParser(base_abs)
        
    while len(current) >= len(base_abs):
        if is_actual_project_root(current, ignore_parser, base_dir=base_abs):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None

def schedule_watches(observer, base_path, ignore_parser, event_handler):
    """Walks the base path dynamically, respecting ignores, and schedules non-recursive watches."""
    watch_count = 0
    try:
        observer.schedule(event_handler, path=base_path, recursive=False)
        watch_count += 1
    except Exception as e:
        print(f"[Watcher] Failed to watch base path {base_path}: {e}")
        
    for root, dirs, files in os.walk(base_path, topdown=True):
        ignore_parser.load_gitignore(root)
        
        # Filter dirs in-place to respect ignores
        filtered = []
        for d in dirs:
            full_path = os.path.join(root, d)
            if not ignore_parser.is_ignored(full_path, is_dir=True):
                filtered.append(d)
        dirs[:] = filtered
        
        # Register watch for root directory
        if root != base_path:
            try:
                observer.schedule(event_handler, path=root, recursive=False)
                watch_count += 1
            except Exception:
                pass
                
    print(f"[Watcher] Successfully scheduled {watch_count} directory watches.")

class ProjectChangeHandler(FileSystemEventHandler):
    """Listens for file changes and triggers immediate reviews."""
    def __init__(self, base_path, ignore_parser, self_path, start_mtime, mode="analyze", observer=None):
        self.base_path = base_path
        self.ignore_parser = ignore_parser
        self.self_path = os.path.abspath(self_path)
        self.start_mtime = start_mtime
        self.last_triggered = {}
        self.mode = mode
        self.observer = observer
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        filepath = os.path.abspath(event.src_path)
        
        # Immediate self-reload check if the script itself was modified
        if filepath == self.self_path:
            try:
                current_mtime = os.path.getmtime(self.self_path)
                if current_mtime > self.start_mtime:
                    print("\n[Watcher] 🔄 Script modification detected. Restarting script dynamically...")
                    os.execv(sys.executable, [sys.executable] + sys.argv)
            except Exception as e:
                print(f"[Watcher] Error restarting: {e}")
                
        # Skip if ignored
        if self.ignore_parser.is_ignored(filepath):
            return
            
        # Only trigger review for standard source code files
        ext = os.path.splitext(filepath)[1]
        if ext not in [".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".css", ".go", ".rs", ".cpp", ".c", ".h"]:
            return
            
        # Throttle quick saves (within 2 seconds)
        now = time.time()
        if filepath in self.last_triggered and now - self.last_triggered[filepath] < 2:
            return
        self.last_triggered[filepath] = now
        
        print(f"\n[Watcher] 📝 Change detected in: {filepath}")
        project_root = find_parent_project_root(filepath, self.base_path, self.ignore_parser)
        if project_root:
            print(f"[Watcher] 🔍 Triggering immediate review for project: {os.path.basename(project_root)}")
            self.ignore_parser.load_gitignore(project_root)
            try:
                run_project_review(project_root, self.ignore_parser, mode=self.mode, base_path=self.base_path)
            except Exception as e:
                print(f"[Watcher] Error during immediate project review: {e}")

    def on_created(self, event):
        if event.is_directory and self.observer:
            dir_path = os.path.abspath(event.src_path)
            if not self.ignore_parser.is_ignored(dir_path, is_dir=True):
                try:
                    self.observer.schedule(self, path=dir_path, recursive=False)
                    print(f"[Watcher] ➕ Dynamically watching new directory: {dir_path}")
                except Exception:
                    pass

def main():
    default_base = os.path.dirname(ORCHESTRATOR_DIR)
    parser = argparse.ArgumentParser(description="Multi-Project Code Review & Self-Healing Loop")
    parser.add_argument("--base", type=str, default=default_base, help="Base workspace path to traverse")
    parser.add_argument("--loop", action="store_true", help="Run continuously in a watcher loop")
    parser.add_argument("--interval", type=int, default=300, help="Interval in seconds between runs in loop mode (default: 300)")
    parser.add_argument("--watch", action="store_true", help="Watch base directory for immediate file modifications and review dynamically")
    parser.add_argument("--mode", type=str, choices=["review", "analyze"], default="analyze", help="Mode: 'review' (bug finding & auto-fix) or 'analyze' (tech spec & architecture report)")
    
    args = parser.parse_args()
    
    base_path = os.path.abspath(args.base)
    if not os.path.exists(base_path):
        print(f"Error: Base directory '{base_path}' does not exist.")
        sys.exit(1)
        
    self_path = os.path.abspath(__file__)
    start_mtime = os.path.getmtime(self_path)
    
    if args.watch:
        print("\n==================================================")
        print(f"👁️ Starting Dynamic Event-Driven Watcher Mode on {base_path}")
        print("==================================================")
        
        ignore_parser = GitIgnoreParser(base_path)
        observer = Observer()
        event_handler = ProjectChangeHandler(base_path, ignore_parser, self_path, start_mtime, mode=args.mode, observer=observer)
        
        # Schedule watches selectively to avoid inotify exhaustion
        print("[Watcher] Initializing gitignore boundary definitions and scheduling watches...")
        schedule_watches(observer, base_path, ignore_parser, event_handler)
        
        try:
            observer.start()
        except OSError as e:
            if e.errno == 28 or "inotify" in str(e).lower():
                print("\n[Watcher] ❌ Error: Linux inotify watch limit reached.")
                print("[Watcher] The directory tree you are trying to watch is too large for the system's current limit.")
                print("[Watcher] To temporarily increase the limit, run:")
                print("    sudo sysctl fs.inotify.max_user_watches=524288")
                print("[Watcher] To make this permanent, run:")
                print("    echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && sudo sysctl -p")
                sys.exit(1)
            else:
                raise e
        
        print("[Watcher] System actively listening for file saves. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
        sys.exit(0)
        
    while True:
        # Check if the script itself was modified and restart if so
        try:
            current_mtime = os.path.getmtime(self_path)
            if current_mtime > start_mtime:
                print("\n[Master] 🔄 Script modification detected. Restarting script dynamically...")
                os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"[Master] Error checking self modification: {e}")

        print("\n==================================================")
        print(f"🚀 Starting Code Analysis Cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("==================================================")
        
        # Instantiate dynamic gitignore and crawler
        ignore_parser = GitIgnoreParser(base_path)
        roots = find_project_roots(base_path, ignore_parser)
        print(f"[Master] Found {len(roots)} projects to review.")
        
        for r in roots:
            try:
                run_project_review(r, ignore_parser, mode=args.mode, base_path=base_path)
            except Exception as e:
                print(f"[Master] Unexpected error analyzing {r}: {e}")
                
        if not args.loop:
            break
            
        print(f"\n[Master] Sleeping for {args.interval} seconds until next scan cycle...")
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
