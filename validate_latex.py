import re
import sys

def validate_latex(filepath):
    print(f"Validating LaTeX Syntax for {filepath}...")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

    errors = []

    # 1. Check matching environments using a stack
    # Find all \begin{...} and \end{...}
    tokens = re.findall(r'\\(begin|end)\{([a-zA-Z\*]+)\}', content)
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

    # 2. Check braces balance using a stack (ignoring escaped \{ and \})
    # Remove escaped braces
    clean_content = re.sub(r'\\\{', '', content)
    clean_content = re.sub(r'\\\}', '', clean_content)
    
    # We only care about '{' and '}'
    brace_stack = []
    for idx, char in enumerate(clean_content):
        if char == '{':
            brace_stack.append(idx)
        elif char == '}':
            if not brace_stack:
                # Find line number for display
                line_no = clean_content[:idx].count('\n') + 1
                errors.append(f"Unmatched closing brace '}}' around line {line_no}")
            else:
                brace_stack.pop()

    for pos in brace_stack:
        line_no = clean_content[:pos].count('\n') + 1
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
        filepath = "/home/chitrarth/Chitrarth/Project P/overleaf/main.tex"
    else:
        filepath = sys.argv[1]
    success = validate_latex(filepath)
    sys.exit(0 if success else 1)
