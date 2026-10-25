# memory-folders

A directory tree of switchable **memory stores** for OpenLumara's `memory` module.

Normally OpenLumara keeps one flat pile of memories. This module augments the memory
module so memories live in **store directories** that you can nest and switch between:

```
<data>/memory_stores/
├── active_store          <- which store is currently active
└── root/                 <- the root memory store (your existing memories migrate here)
    ├── memory.mp
    ├── work/             <- a sub-store
    │   ├── memory.mp
    │   └── projects/     <- stores can nest arbitrarily deep
    │       └── memory.mp
    └── personal/
        └── memory.mp
```

## How it works

- **Root store** — on first run the module moves the memory module's default store
  (`<data>/memory.mp`) into `root/memory.mp`, so nothing is lost.
- **Creating stores** — create a store directory inside any existing store
  (tool `memory-folders_create_store`, or `/memory-store create <parent> <name>`).
- **Activating a store** — activating a store instantly switches which memories are
  loaded: the store's own memories **plus all memories in its sub-stores** become
  active and available everywhere (memory tools, search, pinned memories in the
  system prompt, the WebUI memory sidebar). Do it with
  `memory-folders_activate_store` or `/memory-store activate <path>`.
- **Writes** — new memories created with the normal memory tools are saved into the
  active store's own directory (never into sub-stores).
- **Scoping** — activating a sub-store does *not* include the memories of its
  parent stores: only the store itself and its sub-stores are active. To see
  everything again, activate `root`.
- **Deleting** — `delete_store` removes a store and everything nested in it; it
  refuses to touch non-empty stores unless `force=True`, and never deletes `root`.

The regular memory tools (`memory_create`, `memory_edit`, `memory_search`, ...) keep
working untouched — the module transparently swaps the memory module's storage for a
view over the active store subtree, and re-attaches itself if the memory module
reloads. Disable/reload this module and the memory module is handed back its
original storage. If you use the memory module while `memory-folders` is disabled,
any memories created in the meantime are merged back into the root store on next
startup.

## Tools

| Tool | Description |
|---|---|
| `memory-folders_list_stores` | Tree of all stores with memory counts, active one marked |
| `memory-folders_create_store` | Create a store inside an existing store |
| `memory-folders_activate_store` | Switch the active store (its subtree becomes active) |
| `memory-folders_delete_store` | Delete a store and its sub-stores (needs `force` if non-empty) |

## Commands

```
/memory-store                          # list the tree
/memory-store activate root/work       # switch stores (bare 'work' also works)
/memory-store create root work         # create a sub-store
/memory-store delete work [force]      # remove a store subtree
```

## WebUI

With the WebUI channel enabled, the module ships a **Memory Stores** sidebar tab
(next to the memory panel tab): the store tree with per-store memory counts, the
active store highlighted, one-click activation, and delete buttons with
confirmation (a second confirmation when the store still contains memories).
New stores are created via the "+" button on the intended parent store's row:
it opens a modal that takes the store name and has Cancel/Create buttons. It can be turned off with the auto-added
`enable_webui_extension` setting. Activating or deleting a store from this tab
also force-refreshes the memory panel (memories, tags and search results), so
the two tabs never disagree. Switches made from chat (tools/`/memory-store`)
are not pushed to the browser — the memory panel picks them up on its own
refresh.

## Settings

| Setting | Default | Description |
|---|---|---|
| `stores_folder` | `memory_stores` | Folder in the data dir that holds the store tree |
| `show_active_store_prompt` | `true` | Tell the AI at the end of context which store is active |

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
  `deleted_memories` trash — it is not split per store.
- In `--tmp` mode the store tree is read but nothing is written to disk, and
  creating/deleting stores is disabled.

## License

Copyright (C) 2026 theunknownmuncher <theunknownmuncher@protonmail.com>

GPL-3.0-or-later (see `LICENSE`).
