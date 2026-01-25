import pytest
import subprocess
import sys
from pathlib import Path

# Assuming toolbox.py is in the same directory and can be imported or run
# For this simple test, we'll just check if the file exists and is executable-ish
# In a real scenario, we'd import the module, but toolbox.py has a main() that runs on import if we aren't careful,
# or we need to refactor toolbox.py to be importable without side effects.
# For now, let's just test the valid_tool regex or similar logic if we can extract it, 
# or just check file presence.

def test_toolbox_exists():
    p = Path("toolbox.py")
    assert p.exists() or Path("git/toolbox/toolbox.py").exists()

def test_syntax_valid():
    """Ensure the script compiles as valid Python"""
    tool_path = "toolbox.py"
    if not Path(tool_path).exists():
        tool_path = "git/toolbox/toolbox.py"
    
    # Compile the file to check for syntax errors
    with open(tool_path, "r") as f:
        source = f.read()
    compile(source, tool_path, "exec")
