# memory-folders

A directory tree of switchable **memory folders** for OpenLumara's `memory`
module.

Normally OpenLumara keeps one flat pile of memories. This module augments the memory
module so memories live in **folder directories** that you can nest and switch between:

```
<data>/memory_folders/
├── active_folder          <- which folder is currently active
└── root/                  <- the root memory folder (your existing memories migrate here)
    ├── memory.mp
    ├── work/             <- a sub-folder
    │   ├── memory.mp
    │   └── projects/     <- folders can nest arbitrarily deep
    │       └── memory.mp
    └── personal/
        └── memory.mp
```

## How it works

- **Root folder** — on first run the module moves the memory module's default memory
  file (`<data>/memory.mp`) into `root/memory.mp`, so nothing is lost.
- **Creating folders** — create a folder directory inside any existing folder
  (tool `memory-folders_create_folder`, or `/memory-folder create <parent> <name>`).
- **Activating a folder** — activating a folder instantly switches which memories are
  loaded: the folder's own memories **plus all memories in its sub-folders** become
  active and available everywhere (memory tools, search, pinned memories in the
  system prompt, the WebUI memory sidebar). Do it with
  `memory-folders_activate_folder` or `/memory-folder activate <path>`.
- **Writes** — new memories created with the normal memory tools are saved into the
  active folder's own directory (never into sub-folders).
- **Scoping** — activating a sub-folder does *not* include the memories of its
  parent folders: only the folder itself and its sub-folders are active. To see
  everything again, activate `root`.
- **Deleting** — `delete_folder` removes a folder and everything nested in it; it
  refuses to touch non-empty folders unless `force=True`, and never deletes `root`.

The regular memory tools (`memory_create`, `memory_edit`, `memory_search`, ...) keep
working untouched — the module transparently swaps the memory module's storage for a
view over the active folder subtree, and re-attaches itself if the memory module
reloads. Disable/reload this module and the memory module is handed back its
original storage. If you use the memory module while `memory-folders` is disabled,
any memories created in the meantime are merged back into the root folder on next
startup.

## Tools

| Tool | Description |
|---|---|
| `memory-folders_list_folders` | Tree of all folders with memory counts, active one marked |
| `memory-folders_create_folder` | Create a folder inside an existing folder |
| `memory-folders_activate_folder` | Switch the active folder (its subtree becomes active) |
| `memory-folders_delete_folder` | Delete a folder and its sub-folders (needs `force` if non-empty) |

## Commands

```
/memory-folder                          # list the tree
/memory-folder activate root/work       # switch folders (bare 'work' also works)
/memory-folder create root work         # create a sub-folder
/memory-folder delete work [force]      # remove a folder subtree
```

## WebUI

With the WebUI channel enabled, the module ships a **Memory Folders** sidebar tab
(next to the memory panel tab):

- the folder tree with per-folder memory counts (own / subtree), active folder
  highlighted
- one-click activation by clicking a folder name
- creation via the "+" button on the intended parent folder's row, which opens a
  compact modal with a name input and Cancel/Create buttons
- delete buttons with confirmation, plus a second confirmation when the folder
  still contains memories
- activating or deleting from this tab also force-refreshes the memory panel
  (memories, tags and search results), so the two tabs never disagree

Switches made from chat (tools or `/memory-folder`) are not pushed to the browser;
the memory panel picks them up on its own refresh. The whole extension can be
turned off with the auto-added `enable_webui_extension` setting.

## Settings

| Setting | Default | Description |
|---|---|---|
| `folders_folder` | `memory_folders` | Folder in the data dir that holds the folder tree |
| `show_active_folder_prompt` | `true` | Tell the AI at the end of context which folder is active. The text is stable between folder switches (no memory counts) to stay prompt-cache friendly; counts are available on demand via `list_folders`. |
| `enable_webui_extension` | `true` | Auto-added by the framework; toggles the Memory Folders sidebar tab and its API routes |

## Files

```
module.py                                  <- module + /api/ext/memory-folders routes
webui/templates/sidebars/memory_folders.html   <- sidebar tab (tab label comes from this filename)
webui/templates/sidebars/memory_folders.svg    <- tab icon
webui/templates/modals/memory_folder_create.html <- new-folder modal
webui/assets/js/memory_folders.js           <- tab logic (Alpine state "memoryFolders")
webui/assets/css/memory_folders.css         <- tab + modal styles
LICENSE                                    <- GPL-3.0-or-later
README.md                                  <- this file
.gitignore                                 <- python/editor/OS artifacts
```

## Install

1. Put this folder in OpenLumara's user modules directory
   (default `openlumara/user_modules/`, or wherever `user_modules.path` points).
   `~/user_modules/memory-folders` works too — symlink it in:
   `ln -s ~/user_modules/memory-folders <openlumara>/user_modules/memory-folders`
2. Restart OpenLumara.
3. Enable it: `/module memory-folders` (then `/restart`), or tick it in the WebUI
   settings. `memory` must also be enabled.

## Notes

- Deleted memories (`memory_delete`) still go to the memory module's global
  `deleted_memories` trash — it is not split per folder.
- In `--tmp` mode the folder tree is read but nothing is written to disk, and
  creating/deleting folders is disabled.
- WebUI template changes are picked up at startup or after a settings save;
  JS/CSS changes only need a browser reload (hard-reload if cached).

## License

Copyright (C) 2026 theunknownmuncher <theunknownmuncher@protonmail.com>

GPL-3.0-or-later (see `LICENSE`).
