# memory-folders module for OpenLumara — a directory tree of switchable memory stores for the memory module
# Copyright (C) 2026 theunknownmuncher <theunknownmuncher@protonmail.com>
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# -- AI GENERATED CODE (Qwen3.8 Flash Next) :: (2026-10-24)
import core
import channels.webui.api as webui
import os
import re
import shutil

ROOT_STORE = "root"
STORE_FILE = "memory.mp"  # matches StorageList("memory", type="msgpack") used by the memory module

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,63}$")


def _valid_name(name):
    return isinstance(name, str) and _NAME_RE.match(name) and name not in (".", "..")


class StoreView(list):
    """
    Drop-in replacement for the memory module's `StorageList("memory")`.

    Aggregates the memory files of every store directory that is active
    (the active store itself plus all stores nested inside it) into one
    list. Reads, searches and
    deletions span the whole active subtree; new memories are appended to
    the active store's own file. All mutations only persist when `save()`
    is called, mirroring StorageList semantics.
    """

    def __init__(self, module):
        list.__init__(self)
        self.module = module

        # mirror the StorageList attributes the memory module may touch
        self.name = "memory"
        self.type = "msgpack"
        self.ext = "mp"
        self.binary = True
        self.path = ""

        self._owners = []       # store directory each entry in this list belongs to
        self._loaded_dirs = []  # store directories backing this view (own dir last)
        self._own_dir = ""      # the active store's own directory (where new memories go)
        self._backends = {}     # store dir -> StorageList
        self.load()

    # -- backend helpers ------------------------------------------------

    def invalidate(self):
        """drop cached backends (after the tree or the stores folder changed)"""
        self._backends.clear()

    def _backend(self, store_dir):
        backend = self._backends.get(store_dir)
        if backend is None:
            backend = core.storage.StorageList("memory", type="msgpack", path=store_dir, autoload=False)
            self._backends[store_dir] = backend
        return backend

    # -- StorageList-compatible interface -------------------------------

    def load(self, data=None):
        if data is not None:
            # StorageList compat: replacing the whole list targets the active store itself
            own = self._own_dir or self.module._active_own_dir()
            backend = self._backend(own)
            backend.load()
            backend.clear()
            backend.extend(data)
            backend.save()
            data = None  # fall through to a normal rebuild

        dirs = self.module._active_store_dirs()
        if not dirs:
            self.clear()
            self._owners = []
            self._loaded_dirs = []
            self._own_dir = ""
            self.path = ""
            return self

        own = dirs[-1]  # _active_store_dirs always puts the active store last
        entries, owners = [], []
        for store_dir in dirs:
            backend = self._backend(store_dir)
            if not core.storage.TEMPORARY:
                backend.load()
            for mem in backend:
                if isinstance(mem, dict):
                    entries.append(mem)
                    owners.append(store_dir)

        self.clear()
        list.extend(self, entries)
        self._owners = owners
        self._loaded_dirs = dirs
        self._own_dir = own
        self.path = os.path.join(own, STORE_FILE)
        return self

    def save(self):
        groups = {}
        for mem, store_dir in zip(list(self), self._owners):
            groups.setdefault(store_dir, []).append(mem)

        for store_dir in self._loaded_dirs:
            backend = self._backend(store_dir)
            backend.clear()
            backend.extend(groups.get(store_dir, []))
            backend.save()  # no-op while in temporary mode, like StorageList.save()
        return True

    def append(self, mem):
        list.append(self, mem)
        self._owners.append(self._own_dir)

    def insert(self, index, mem):
        list.insert(self, index, mem)
        i = index if index >= 0 else max(0, len(self._owners) + index)
        self._owners.insert(min(i, len(self._owners)), self._own_dir)

    def pop(self, index=-1):
        i = index if index >= 0 else len(self) + index
        mem = list.pop(self, index)
        if 0 <= i < len(self._owners):
            self._owners.pop(i)
        elif len(self._owners) > len(self):
            self._owners = self._owners[: len(self)]
        return mem

    def get(self, *args, **kwargs):
        self.load()
        return list.__getitem__(self, args[0])

    async def search(self, query, field_weights=None, top_n=10):
        """ranked text search across every active store"""
        self.load()
        return await core.search.search(list(self), query, field_weights=field_weights, top_n=top_n)

    # -- extras used by this module --------------------------------------

    def store_counts(self):
        """returns {store relative path: entry count} for the stores in this view"""
        counts = {}
        for store_dir in self._loaded_dirs:
            rel = self.module._rel(store_dir)
            counts[rel] = sum(1 for d in self._owners if d == store_dir)
        return counts

    def breakdown(self):
        """human-readable per-store breakdown of this view"""
        parts = []
        for store_dir in self._loaded_dirs:
            rel = self.module._rel(store_dir)
            count = sum(1 for d in self._owners if d == store_dir)
            marker = "  <- where new memories are saved" if store_dir == self._own_dir else ""
            parts.append(f"  {rel}: {count} memories{marker}")
        return "\n".join(parts)


class MemoryFolders(core.module.Module):
    """Augments the memory module with a directory tree of memory stores: create stores inside stores, then activate any store to instantly switch which memories (its own plus all its sub-stores' ones) are active and available.

    Each memory store is a directory holding its own memory file, with the 'root' store as the base of the tree. Activating a store makes its memories and all memories of stores nested inside it active; new memories are saved into the active store itself. The default memory tools (create, edit, search, ...) keep working — they simply operate on the active store subtree. The user's existing memories are migrated into the root store automatically on first run."""

    category = "memory"

    settings = {
        "stores_folder": {
            "type": "string",
            "default": "memory_stores",
            "description": "Folder inside OpenLumara's data directory that holds the memory store directories. The 'root' store inside it is the base of the tree.",
        },
        "show_active_store_prompt": {
            "default": True,
            "description": "Tell the AI which memory store is currently active at the end of the context, so it always knows where its memories live and where new ones are saved.",
        },
    }

    # -------------------------
    #   LIFECYCLE
    # -------------------------

    async def on_ready(self):
        self._view = None
        self._stores_root = None
        self._active_text_obj = None

        self._setup()
        self._view = StoreView(self)
        self._attach()

        if "memory" not in self.manager.modules:
            self.log(self.name, "WARNING: the memory module is not enabled — memory stores will have no effect until it is.")

        self.log(self.name, f"memory stores ready (active: {self._active_path()}, tree root: {self._stores_root})")

    async def on_shutdown(self):
        # hand the memory module back its own storage so disabling this module degrades gracefully
        mem = self.manager.modules.get("memory") if self.manager else None
        if mem is not None and self._view is not None and getattr(mem, "_mem", None) is self._view:
            mem._mem = core.storage.StorageList("memory", type="msgpack")
        self._view = None

    async def on_end_prompt(self):
        # cheap self-heal: if the memory module was reloaded, its on_ready reset _mem — re-attach
        self._attach()
        if self._view is None or self.manager.modules.get("memory") is None:
            return None
        if not self.config.get("show_active_store_prompt"):
            return None

        # prompt-cache optimization: this message is rebuilt at the end of the context on
        # every request, so it must stay byte-identical between store switches. memory
        # counts and per-store breakdowns are deliberately NOT included — they change on
        # every memory write and would break prefix cache matches. counts are available
        # on demand via list_stores.
        active = self._active_path()
        return (
            f"Memory stores are active: the currently active store is '{active}'. "
            f"New memories are saved to it, and the memories available to your memory tools are those of '{active}' plus all stores nested inside it. "
            f"Switch or create stores with the memory store tools or the /memory-store command."
        )

    # -------------------------
    #   AI TOOLS
    # -------------------------

    async def list_stores(self):
        """Lists every memory store directory as a tree, with memory counts and the active store marked.

        Returns:
            a tree of all stores: own memory count and total count including sub-stores
        """
        self._setup()
        stores = self._discover()
        if not stores:
            return self.result("no memory stores found (the root store is missing!)", success=False)

        counts = {d: len(self._read_store(d)) for d in stores}
        active_path = self._active_path()
        active_dir = self._safe_store_dir(active_path)

        lines = ["memory stores (path — memories here / total in subtree):"]
        for d in stores:
            rel = self._rel(d)
            depth = rel.count("/")
            subtree = sum(c for o, c in counts.items() if o == d or o.startswith(d + os.sep))
            mark = "  [ACTIVE]" if d == active_dir else ""
            lines.append(f"{'  ' * depth}{rel} — {counts[d]} / {subtree}{mark}")

        return self.result("\n".join(lines))

    async def create_store(self, parent: str, name: str):
        """Creates a new memory store directory inside an existing memory store.

        Args:
            parent: path of the existing store that will contain the new one (e.g. 'root' or 'root/work')
            name: name of the new store directory (e.g. 'work'); letters, numbers, spaces, dashes, underscores and dots are allowed
        """
        try:
            parts = self._parse_path(parent)
            parent_dir = self._store_dir(parts)
        except ValueError as e:
            return self.result(str(e), success=False)

        name = str(name or "").strip()
        if not _valid_name(name):
            return self.result(f"invalid store name '{name}' — must start with a letter or number and may contain letters, numbers, spaces, dashes, underscores and dots", success=False)

        if not self._is_store(parent_dir):
            return self.result(f"parent store '{'/'.join(parts)}' does not exist — use list_stores to see the tree", success=False)

        child = os.path.join(parent_dir, name)
        if os.path.exists(child):
            return self.result(f"a directory '{name}' already exists inside '{'/'.join(parts)}'", success=False)

        if core.storage.TEMPORARY:
            return self.result("store creation is disabled while running in temporary mode", success=False)

        os.makedirs(child, exist_ok=False)
        core.storage.StorageList("memory", type="msgpack", path=child, autoload=False)  # creates the empty memory.mp

        self._refresh()
        new_path = "/".join(parts + [name])
        return self.result(f"created memory store '{new_path}' (empty). Activate it with activate_store('{new_path}') to start saving memories to it.")

    async def activate_store(self, path: str):
        """Switches which memory store is active. All memories of that store and of every store nested inside it become active and available; new memories are saved into the activated store itself.

        Args:
            path: the store to activate (e.g. 'root', 'root/work' or just 'work' — paths are relative to the root store)
        """
        try:
            parts = self._parse_path(path)
            store_dir = self._store_dir(parts)
        except ValueError as e:
            return self.result(str(e), success=False)

        if not self._is_store(store_dir):
            return self.result(f"memory store '{'/'.join(parts)}' doesn't exist — use list_stores to see the tree", success=False)

        self._active_text().set("/".join(parts))
        self._refresh()

        active = self._active_path()
        total = len(self._view)
        breakdown = self._view.breakdown()
        return self.result(f"active memory store: '{active}' — {total} memories active:\n{breakdown}")

    async def delete_store(self, path: str, force: bool = False):
        """Deletes a memory store directory and every store nested inside it. DANGEROUS: memories are removed from disk.

        Args:
            path: the store to delete (the 'root' store cannot be deleted)
            force: set to True to also delete when the stores still contain memories
        """
        try:
            parts = self._parse_path(path)
            store_dir = self._store_dir(parts)
        except ValueError as e:
            return self.result(str(e), success=False)

        if parts == [ROOT_STORE]:
            return self.result("the root store cannot be deleted", success=False)

        if not self._is_store(store_dir):
            return self.result(f"memory store '{'/'.join(parts)}' doesn't exist", success=False)

        if core.storage.TEMPORARY:
            return self.result("store deletion is disabled while running in temporary mode", success=False)

        subtree = [d for d in self._discover() if d == store_dir or d.startswith(store_dir + os.sep)]
        counts = {self._rel(d): len(self._read_store(d)) for d in subtree}
        total = sum(counts.values())

        if total and not force:
            detail = ", ".join(f"{k}: {v}" for k, v in counts.items() if v)
            return self.result(f"refusing to delete: {total} memories would be lost ({detail}). Pass force=True to delete anyway.", success=False)

        # if the active store lives inside the doomed subtree, fall back to root first
        active_path = self._active_path()
        active_dir = self._safe_store_dir(active_path)
        if active_dir and (active_dir == store_dir or active_dir.startswith(store_dir + os.sep)):
            self._active_text().set(ROOT_STORE)

        shutil.rmtree(store_dir)

        self._refresh()
        return self.result(f"deleted memory store '{'/'.join(parts)}' ({total} memories removed across {len(subtree)} store(s)). Active store: '{self._active_path()}'")

    # -- AI GENERATED CODE (Qwen3.8 Flash Next) :: (2026-10-24)
    # webui extension routes for the memory store sidebar panel. Private
    # methods are ignored by the tool loader; @webui.route exposes them under
    # /api/ext/memory-folders/<path>.

    @webui.route("tree")
    async def _route_tree(self, body=None, query=None):
        """store tree for the sidebar panel"""
        self._setup()
        stores = self._discover()
        counts = {d: len(self._read_store(d)) for d in stores}

        active_dir = self._safe_store_dir(self._active_path())
        if active_dir not in counts:
            active_dir = os.path.join(self._stores_root, ROOT_STORE)

        items = []
        for store_dir in stores:
            rel = self._rel(store_dir)
            items.append({
                "path": rel,
                "name": rel.rsplit("/", 1)[-1],
                "depth": rel.count("/"),
                "own": counts[store_dir],
                "subtree": sum(c for o, c in counts.items() if o == store_dir or o.startswith(store_dir + os.sep)),
                "active": store_dir == active_dir,
            })

        active_total = sum(c for o, c in counts.items() if o == active_dir or o.startswith(active_dir + os.sep))
        return {"active": self._rel(active_dir), "total_active": active_total, "stores": items}

    @webui.route("activate", method="POST")
    async def _route_activate(self, body=None, query=None):
        path = str((body or {}).get("path", "")).strip()
        if not path:
            return self.result("no memory store path given", success=False)
        return await self.activate_store(path)

    @webui.route("create", method="POST")
    async def _route_create(self, body=None, query=None):
        body = body or {}
        parent = str(body.get("parent", "")).strip()
        name = str(body.get("name", "")).strip()
        if not parent or not name:
            return self.result("both a parent store and a name are required", success=False)
        return await self.create_store(parent, name)

    @webui.route("delete", method="POST")
    async def _route_delete(self, body=None, query=None):
        body = body or {}
        path = str(body.get("path", "")).strip()
        if not path:
            return self.result("no memory store path given", success=False)
        return await self.delete_store(path, force=bool(body.get("force")))

    # -------------------------
    #   USER-FACING COMMANDS
    # -------------------------

    @core.module.command("memory-store", help={
        "": "Lists all memory stores and marks the active one",
        "activate <path>": "Switch the active memory store, e.g. '/memory-store activate root/work'",
        "create <parent> <name>": "Create a store inside an existing one, e.g. '/memory-store create root work'",
        "delete <path> [force]": "Delete a store and its sub-stores, e.g. '/memory-store delete work force'",
    })
    async def memory_store_command(self, args: list):
        args = [str(a) for a in (args or [])]
        if not args:
            return (await self.list_stores())["content"]

        sub = args[0].lower()
        if sub == "activate" and len(args) >= 2:
            return (await self.activate_store(" ".join(args[1:])))["content"]
        if sub == "create" and len(args) >= 3:
            return (await self.create_store(" ".join(args[1:-1]), args[-1]))["content"]
        if sub == "delete" and len(args) >= 2:
            force = args[-1].lower() == "force"
            path_args = args[1:-1] if force else args[1:]
            if not path_args:
                return "usage: /memory-store delete <path> [force]"
            return (await self.delete_store(" ".join(path_args), force))["content"]

        return "usage: /memory-store [activate <path> | create <parent> <name> | delete <path> [force]] (no args lists all stores)"

    # -------------------------
    #   INTERNALS
    # -------------------------

    def _setup(self):
        """ensure the stores tree exists; migrate the default memory store into root once"""
        root = self._stores_root_path()
        if self._stores_root and self._stores_root != root:
            self._active_text_obj = None
            if self._view is not None:
                self._view.invalidate()
        self._stores_root = root

        if core.storage.TEMPORARY:
            return

        root_dir = os.path.join(root, ROOT_STORE)
        os.makedirs(root_dir, exist_ok=True)
        root_file = os.path.join(root_dir, STORE_FILE)
        default_file = os.path.join(core.get_data_path(), "memory.mp")

        if not os.path.exists(root_file):
            if os.path.exists(default_file):
                # one-time migration: the memory module's default store becomes the root store
                shutil.move(default_file, root_file)
                self.log(self.name, "migrated the default memory store into the root store")
            else:
                core.storage.StorageList("memory", type="msgpack", path=root_dir, autoload=False)
        elif os.path.exists(default_file):
            # the memory module was used while this module was disabled — merge anything new into root
            self._merge_into_root(default_file, root_file)

    def _merge_into_root(self, default_file, root_file):
        try:
            old = core.storage.StorageList("memory", type="msgpack", path=os.path.dirname(default_file), autoload=True)
            if len(old) == 0:
                return  # empty leftover (the memory module recreates it on every boot) — ignore
            root_list = core.storage.StorageList("memory", type="msgpack", path=os.path.dirname(root_file), autoload=True)
            existing = {m.get("id") for m in root_list if isinstance(m, dict)}
            added = 0
            for mem in old:
                if isinstance(mem, dict) and mem.get("id") not in existing:
                    root_list.append(mem)
                    added += 1
            if added:
                root_list.save()
                os.remove(default_file)
                self.log(self.name, f"merged {added} memories created while memory-folders was disabled into the root store")
        except Exception as e:
            self.log(self.name, f"could not merge leftover default memory store: {core.detail_error(e)}")

    def _stores_root_path(self):
        folder = str(self.config.get("stores_folder") or "memory_stores").strip().strip("/\\")
        parts = [p for p in folder.replace("\\", "/").split("/") if p not in ("", ".", "..")]
        if not parts or any(not _valid_name(p) for p in parts):
            parts = ["memory_stores"]
        return os.path.join(core.get_data_path(), *parts)

    def _parse_path(self, path):
        """turns 'work' or 'root/work/projects' into ['root','work','projects']; raises ValueError on junk"""
        raw = str(path or "").strip().replace("\\", "/")
        parts = [p for p in raw.split("/") if p not in ("", ".")]
        if not parts:
            raise ValueError("no memory store path given")
        for p in parts:
            if not _valid_name(p):
                raise ValueError(f"invalid store name '{p}' — letters, numbers, spaces, dashes, underscores and dots are allowed")
        if parts[0] != ROOT_STORE:
            parts.insert(0, ROOT_STORE)  # bare names like 'work' live under root
        return parts

    def _store_dir(self, parts):
        d = os.path.join(self._stores_root, *parts)
        base = os.path.realpath(self._stores_root)
        real = os.path.realpath(d)
        if real != base and not real.startswith(base + os.sep):
            raise ValueError("store path escapes the memory stores folder")
        return d

    def _safe_store_dir(self, path):
        try:
            return self._store_dir(self._parse_path(path))
        except ValueError:
            return None

    def _rel(self, store_dir):
        return os.path.relpath(store_dir, self._stores_root).replace(os.sep, "/")

    def _is_store(self, store_dir):
        return os.path.isfile(os.path.join(store_dir, STORE_FILE))

    def _read_store(self, store_dir):
        backend = core.storage.StorageList("memory", type="msgpack", path=store_dir, autoload=False)
        if not core.storage.TEMPORARY:
            backend.load()
        return list(backend)

    def _discover(self):
        """all store directories, root first, then nested stores alphabetically (depth-first)"""
        found = []

        def walk(directory):
            found.append(directory)
            try:
                entries = sorted(os.listdir(directory), key=str.lower)
            except OSError:
                return
            for entry in entries:
                sub = os.path.join(directory, entry)
                if os.path.isdir(sub) and self._is_store(sub):
                    walk(sub)

        root_dir = os.path.join(self._stores_root, ROOT_STORE)
        if self._is_store(root_dir):
            walk(root_dir)
        return found

    def _active_text(self):
        if self._active_text_obj is None:
            self._active_text_obj = core.storage.StorageText("active_store", path=self._stores_root)
        return self._active_text_obj

    def _active_store_parts(self):
        try:
            return self._parse_path(self._active_text().get())
        except ValueError:
            return [ROOT_STORE]

    def _active_path(self):
        return "/".join(self._active_store_parts())

    def _active_own_dir(self):
        d = self._safe_store_dir(self._active_path())
        return d if d and self._is_store(d) else os.path.join(self._stores_root, ROOT_STORE)

    def _active_store_dirs(self):
        """directories backing the view: [sub-stores...] [own store last]"""
        if self._stores_root is None:
            self._setup()

        own = self._active_own_dir()
        all_stores = self._discover()
        if own not in all_stores:
            own = os.path.join(self._stores_root, ROOT_STORE)

        dirs = [d for d in all_stores if d != own and d.startswith(own + os.sep)]
        dirs.append(own)
        return dirs

    def _refresh(self):
        """rebuild the view after the tree or active store changed, and make sure it's attached"""
        if self._view is not None:
            self._view.invalidate()
            self._view.load()
        self._attach()

    def _attach(self):
        """swap the memory module's storage for our view (re-done if memory was reloaded)"""
        if self._view is None or not self.manager:
            return None
        mem = self.manager.modules.get("memory")
        if mem is None:
            return None
        if getattr(mem, "_mem", None) is not self._view:
            mem._mem = self._view
            self.log(self.name, "attached memory store view to the memory module")
        return mem
