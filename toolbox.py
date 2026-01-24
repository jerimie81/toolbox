#!/usr/bin/env python3
"""
toolbox-manager (v2, self-contained, venv-enabled)

- Auto-creates and uses a Python venv under $HOME/.tools/toolbox/venv
- Builds a BusyBox-style multicall binary from C modules
- Hardened, relocatable, recovery-safe
"""

from __future__ import annotations

import os
import sys
import subprocess
import shutil
import re
import tempfile
from pathlib import Path
from typing import List, Optional


# =============================
# Core Configuration
# =============================

APP_NAME = "toolbox"
VERSION = "2.1.0"

ROOT = Path(os.path.expanduser("~")) / ".tools" / APP_NAME
VENV = ROOT / "venv"
TOOLS = ROOT / "tools"
BUILD = ROOT / "build"
BIN = ROOT / "bin"

TOOL_RE = re.compile(r"^[a-z][a-z0-9_]*$")

CFLAGS = [
    "-Wall", "-Wextra", "-Werror",
    "-O2",
    "-fstack-protector-strong",
    "-D_FORTIFY_SOURCE=2",
    "-fPIE",
]
LDFLAGS = ["-pie"]


# =============================
# Venv Bootstrap
# =============================

def ensure_venv():
    if os.environ.get("TOOLBOX_VENV_ACTIVE") == "1":
        return

    ROOT.mkdir(parents=True, exist_ok=True)
    if not VENV.exists():
        print("[*] Creating Python venv:", VENV)
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])

    python = VENV / "bin" / "python"
    if not python.exists():
        sys.exit("[!] venv python missing")

    env = os.environ.copy()
    env["TOOLBOX_VENV_ACTIVE"] = "1"

    os.execve(
        str(python),
        [str(python), *sys.argv],
        env
    )


# =============================
# Utilities
# =============================

def die(msg: str):
    print(f"[!] {msg}", file=sys.stderr)
    sys.exit(1)


def ensure_dirs():
    for d in (ROOT, TOOLS, BUILD, BIN):
        d.mkdir(parents=True, exist_ok=True)


def find_cc() -> str:
    for cc in ("gcc", "clang"):
        path = shutil.which(cc)
        if path:
            return path
    die("No C compiler found (gcc/clang)")


def validate_tool(name: str) -> str:
    if not TOOL_RE.match(name):
        die("Invalid tool name (lowercase, start with letter)")
    return name


def atomic_write(path: Path, data: str):
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent) as f:
        f.write(data)
        tmp = f.name
    os.replace(tmp, path)


def list_tools() -> List[str]:
    return sorted(p.stem for p in TOOLS.glob("*.c"))


# =============================
# Embedded C Templates
# =============================

def tool_template(name: str) -> str:
    return f"""#include <stdio.h>

/* Optional:
 * const char *{name}_desc = "Description";
 */

const char *{name}_help =
    "Usage: {name} [args]\\n"
    "Description: {name} tool.\\n"
    "Options:\\n"
    "  -h, --help  Show this help.\\n";

int {name}_main(int argc, char **argv) {{
    (void)argc; (void)argv;
    printf("Running {name}\\n");
    return 0;
}}
"""


def dispatcher_template(tools: List[str]) -> str:
    decls = []
    entries = []

    for t in tools:
        decls.append(f"int {t}_main(int, char**);")
        decls.append(f"extern const char *{t}_desc __attribute__((weak));")
        decls.append(f"extern const char *{t}_help __attribute__((weak));")
        entries.append(f'    {{"{t}", {t}_main, &{t}_desc, &{t}_help}},')

    return f"""
#include <stdio.h>
#include <string.h>
#include <libgen.h>

#define APP "{APP_NAME}"
#define VER "{VERSION}"

struct Tool {{
    const char *name;
    int (*fn)(int,char**);
    const char **desc;
    const char **help;
}};

{chr(10).join(decls)}

static struct Tool tools[] = {{
{chr(10).join(entries)}
    {{NULL,NULL,NULL,NULL}}
}};

static void help() {{
    printf("%s v%s\\n", APP, VER);
    printf("Usage: %s <cmd> [args]\\n\\n", APP);
    for (int i=0; tools[i].name; i++) {{
        const char *d = (tools[i].desc && *tools[i].desc) ? *tools[i].desc : "";
        printf("  %-16s %s\\n", tools[i].name, d);
    }}
}}

static void tool_help(const char *name) {{
    for (int i=0; tools[i].name; i++) {{
        if (!strcmp(name, tools[i].name)) {{
            if (tools[i].desc && *tools[i].desc)
                printf("%s - %s\\n", name, *tools[i].desc);
            if (tools[i].help && *tools[i].help) {{
                printf("%s\\n", *tools[i].help);
            }} else {{
                printf("Usage: %s [args]\\n", name);
            }}
            return;
        }}
    }}
    printf("Unknown command: %s\\n", name);
}}

static int dispatch(const char *name, int argc, char **argv) {{
    if (argc > 1 && (!strcmp(argv[1], "--help") || !strcmp(argv[1], "-h"))) {{
        tool_help(name);
        return 0;
    }}
    for (int i=0; tools[i].name; i++)
        if (!strcmp(name, tools[i].name))
            return tools[i].fn(argc, argv);
    fprintf(stderr, "Unknown command: %s\\n", name);
    return 1;
}}

int main(int argc, char **argv) {{
    char *prog = basename(argv[0]);

    if (argc > 1 && (!strcmp(argv[1], "--help") || !strcmp(argv[1], "-h"))) {{
        help(); return 0;
    }}

    if (!strcmp(prog, APP)) {{
        if (argc < 2) {{ help(); return 0; }}
        return dispatch(argv[1], argc-1, argv+1);
    }}

    return dispatch(prog, argc, argv);
}}
"""


# =============================
# Commands
# =============================

def cmd_create(name: str):
    name = validate_tool(name)
    path = TOOLS / f"{name}.c"
    if path.exists():
        die("Tool already exists")
    atomic_write(path, tool_template(name))
    print("[+] Created", path)


def cmd_build():
    cc = find_cc()
    tools = list_tools()
    if not tools:
        die("No tools to build")

    main_c = BUILD / "main.c"
    atomic_write(main_c, dispatcher_template(tools))

    out = BUILD / APP_NAME
    cmd = [cc, *CFLAGS, "-o", str(out), str(main_c)]
    cmd += [str(TOOLS / f"{t}.c") for t in tools]
    cmd += LDFLAGS

    print("[*] Building...")
    subprocess.check_call(cmd)

    for t in tools + [APP_NAME]:
        link = BIN / t
        if link.exists():
            link.unlink()
        link.symlink_to(out)

    print("[+] Build complete")
    print(f"    Add to PATH: export PATH=\"{BIN}:$PATH\"")


def menu_select() -> tuple[str, Optional[str]]:
    import curses

    def _menu(stdscr):
        curses.curs_set(0)
        options = ["Create tool", "Build", "List tools", "Exit"]
        idx = 0
        while True:
            stdscr.clear()
            stdscr.addstr(0, 2, "toolbox menu")
            stdscr.addstr(1, 2, "Use arrows or j/k, Enter to select.")
            for i, opt in enumerate(options):
                if i == idx:
                    stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(3 + i, 4, opt)
                if i == idx:
                    stdscr.attroff(curses.A_REVERSE)
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                idx = (idx - 1) % len(options)
            elif key in (curses.KEY_DOWN, ord("j")):
                idx = (idx + 1) % len(options)
            elif key in (10, 13):
                break
        choice = options[idx]
        if choice == "Create tool":
            stdscr.clear()
            stdscr.addstr(0, 2, "Enter tool name:")
            stdscr.refresh()
            curses.echo()
            name = stdscr.getstr(2, 2, 64).decode("utf-8").strip()
            curses.noecho()
            return ("create", name if name else None)
        if choice == "Build":
            return ("build", None)
        if choice == "List tools":
            return ("list", None)
        return ("exit", None)

    return curses.wrapper(_menu)


def cmd_menu():
    while True:
        try:
            if sys.stdin.isatty():
                term = os.environ.get("TERM")
                if not term or term == "dumb":
                    os.environ["TERM"] = "xterm-256color"
            action, name = menu_select()
        except Exception as exc:
            print(f"TUI unavailable ({exc}), falling back to basic menu.")
            return

        if action == "exit":
            return
        if action == "create":
            if not name:
                print("No tool name provided.")
            else:
                try:
                    cmd_create(name)
                except SystemExit as exc:
                    print(exc)
        elif action == "build":
            try:
                cmd_build()
            except Exception as exc:
                print(exc)
        elif action == "list":
            tools = list_tools()
            if tools:
                print("Tools:", ", ".join(tools))
            else:
                print("No tools found.")
        input("Press Enter to continue...")


# =============================
# Entry Point
# =============================

def main():
    ensure_dirs()

    if len(sys.argv) < 2:
        cmd_menu()
        return

    cmd = sys.argv[1]

    if cmd == "create" and len(sys.argv) == 3:
        cmd_create(sys.argv[2])
    elif cmd == "build":
        cmd_build()
    elif cmd == "menu":
        cmd_menu()
    elif cmd == "list":
        tools = list_tools()
        if tools:
            print("\n".join(tools))
    else:
        die("Invalid command")


if __name__ == "__main__":
    ensure_venv()
    main()
