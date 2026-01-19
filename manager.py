import os
import re
import subprocess
import sys

TOOLS_DIR = "./tools"
BUILD_DIR = "./build"
OUTPUT_BIN = "toolbox"

# Ensure directories exist
os.makedirs(TOOLS_DIR, exist_ok=True)
os.makedirs(BUILD_DIR, exist_ok=True)

NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def is_valid_tool_name(name):
    return bool(NAME_PATTERN.match(name))

def create_tool():
    name = input("Enter tool name (e.g., ping): ").strip()
    if not is_valid_tool_name(name):
        print("Invalid name. Use letters, numbers, and underscores, starting with a letter or underscore.")
        return

    path = os.path.join(TOOLS_DIR, f"{name}.c")
    if os.path.exists(path):
        print(f"Tool {name} already exists. Aborting to avoid overwrite.")
        return
    
    content = f"""
#include <stdio.h>
int {name}_main(int argc, char **argv) {{
    printf("Running module: {name}\\n");
    return 0;
}}
"""
    with open(path, "w") as f:
        f.write(content)
    print(f"Tool {name} created.")

def unload_tool():
    name = input("Enter tool name to remove: ").strip()
    if not is_valid_tool_name(name):
        print("Invalid name. Use letters, numbers, and underscores, starting with a letter or underscore.")
        return
    path = os.path.join(TOOLS_DIR, f"{name}.c")
    if os.path.exists(path):
        os.remove(path)
        print(f"{name} removed.")
    else:
        print("Tool not found.")

def construct():
    print("Gathering tools...")
    tools = sorted(
        f[:-2]
        for f in os.listdir(TOOLS_DIR)
        if f.endswith(".c") and is_valid_tool_name(f[:-2])
    )
    
    if not tools:
        print("No tools found. Please 'Load' a tool first.")
        return

    # Generate C Code
    declarations = "\n".join([f"int {t}_main(int argc, char **argv);" for t in tools])
    table_entries = "\n".join([f'    {{"{t}", {t}_main}},' for t in tools])

    c_code = f"""
#include <stdio.h>
#include <string.h>
#include <libgen.h>

{declarations}

struct Tool {{ char *name; int (*func)(int, char**); }};

struct Tool tools[] = {{
{table_entries}
    {{NULL, NULL}}
}};

int main(int argc, char **argv) {{
    char *progname = basename(argv[0]);

    if (strcmp(progname, "{OUTPUT_BIN}") == 0) {{
        printf("Available commands:\\n");
        for (int i = 0; tools[i].name; i++) printf("  %s\\n", tools[i].name);
        return 0;
    }}

    for (int i = 0; tools[i].name; i++) {{
        if (strcmp(progname, tools[i].name) == 0) return tools[i].func(argc, argv);
    }}
    
    printf("Unknown command: %s\\n", progname);
    return 1;
}}
"""
    
    main_path = os.path.join(BUILD_DIR, "main.c")
    with open(main_path, "w") as f:
        f.write(c_code)

    # Compile
    cmd = ["gcc", "-o", OUTPUT_BIN, main_path] + [os.path.join(TOOLS_DIR, t + ".c") for t in tools]
    print("Compiling...")
    try:
        subprocess.check_call(cmd)
        print(f"Success! ./{OUTPUT_BIN} created.")
    except FileNotFoundError:
        print("Compilation Failed: gcc not found. Please install GCC and ensure it is in your PATH.")
    except subprocess.CalledProcessError:
        print("Compilation Failed.")

def main():
    while True:
        print("\n=== Python Builder ===")
        print("1. Construct/Rebuild")
        print("2. Load (Add tool)")
        print("3. Unload (Remove tool)")
        print("4. Exit")
        
        choice = input("Select: ")
        
        if choice == '1': construct()
        elif choice == '2': create_tool()
        elif choice == '3': unload_tool()
        elif choice == '4': sys.exit()
        else: print("Invalid option.")

if __name__ == "__main__":
    main()
    
