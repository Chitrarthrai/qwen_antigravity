import re
import sys
import os

def validate_latex(filepath):
    print(f"Validating LaTeX Syntax for {filepath}...")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

    errors = []

    # 1. Strip comments (lines starting with %, or text after % not escaped by \)
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        comment_match = re.search(r'(?<!\\)%', line)
        if comment_match:
            line = line[:comment_match.start()]
        cleaned_lines.append(line)
    content_no_comments = '\n'.join(cleaned_lines)

    # 2. Check matching environments using a stack
    # Find all \begin{...} and \end{...}
    tokens = re.findall(r'\\(begin|end)\{([a-zA-Z\*]+)\}', content_no_comments)
    stack = []
    
    for action, env in tokens:
        if action == "begin":
            stack.append(env)
        elif action == "end":
            if not stack:
                errors.append(f"Unexpected \\end{{{env}}} with no matching \\begin")
            else:
                last_begun = stack.pop()
                if last_begun != env:
                    errors.append(f"Mismatched environment: \\begin{{{last_begun}}} closed by \\end{{{env}}}")

    while stack:
        unclosed = stack.pop()
        errors.append(f"Unclosed environment: \\begin{{{unclosed}}} has no matching \\end")

    # 3. Check braces balance using a stack (ignoring escaped \{ and \})
    braces_content = re.sub(r'\\\{', '', content_no_comments)
    braces_content = re.sub(r'\\\}', '', braces_content)
    
    brace_stack = []
    for idx, char in enumerate(braces_content):
        if char == '{':
            brace_stack.append(idx)
        elif char == '}':
            if not brace_stack:
                line_no = braces_content[:idx].count('\n') + 1
                errors.append(f"Unmatched closing brace '}}' around line {line_no}")
            else:
                brace_stack.pop()

    for pos in brace_stack:
        line_no = braces_content[:pos].count('\n') + 1
        errors.append(f"Unmatched opening brace '{{' around line {line_no}")

    if errors:
        print("LaTeX Validation: FAILED!")
        for err in errors:
            print(f" - {err}")
        return False
        
    print("LaTeX Validation: PASSED! Stack-based checks confirm all environments and braces are perfectly balanced.")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        ROOT_DIR = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "backend" else SCRIPT_DIR
        PARENT_DIR = os.path.dirname(ROOT_DIR)
        filepath = os.path.join(PARENT_DIR, "overleaf", "main.tex")
    else:
        filepath = sys.argv[1]
    success = validate_latex(filepath)
    sys.exit(0 if success else 1)
