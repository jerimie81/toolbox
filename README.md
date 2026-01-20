# toolbox

`toolbox.py` builds a BusyBox-style multicall binary from C modules.
It bootstraps a venv under `~/.tools/toolbox/venv` and stores tools/build output
under `~/.tools/toolbox`.

## Quick start

Run the TUI menu:

```
./toolbox.py
```

Create a tool module:

```
./toolbox.py create ping
```

Build the multicall binary and symlinks:

```
./toolbox.py build
```

Add the bin directory to your PATH:

```
export PATH="$HOME/.tools/toolbox/bin:$PATH"
```
