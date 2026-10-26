# memory-folders module for OpenLumara — a directory tree of switchable memory folders for the memory module
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

ROOT_FOLDER = "root"
FOLDER_FILE = "memory.mp"  # matches StorageList("memory", type="msgpack") used by the memory module

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,63}$")


def _valid_name(name):
    return isinstance(name, str) and _NAME_RE.match(name) and name not in (".", "..")


class FolderView(list):
    """
    Drop-in replacement for the memory module's `StorageList("memory")`.

    Aggregates the memory files of every folder directory that is active
    (the active folder itself plus all folders nested inside it) into one
    list. Reads, searches and
    deletions span the whole active subtree; new memories are appended to
    the active folder's own file. All mutations only persist when `save()`
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

        self._owners = []       # folder directory each entry in this list belongs to
        self._loaded_dirs = []  # folder directories backing this view (own dir last)
        self._own_dir = ""      # the active folder's own directory (where new memories go)
        self._backends = {}     # folder dir -> StorageList
        self.load()

    # -- backend helpers ------------------------------------------------

    def invalidate(self):
        """drop cached backends (after the tree or the folders folder changed)"""
        self._backends.clear()

    def _backend(self, folder_dir):
        backend = self._backends.get(folder_dir)
        if backend is None:
            backend = core.storage.StorageList("memory", type="msgpack", path=folder_dir, autoload=False)
            self._backends[folder_dir] = backend
        return backend

    # -- StorageList-compatible interface -------------------------------

    def load(self, data=None):
        if data is not None:
            # StorageList compat: replacing the whole list targets the active folder itself
            own = self._own_dir or self.module._active_own_dir()
            backend = self._backend(own)
            backend.load()
            backend.clear()
            backend.extend(data)
            backend.save()
            data = None  # fall through to a normal rebuild

        dirs = self.module._active_folder_dirs()
        if not dirs:
            self.clear()
            self._owners = []
            self._loaded_dirs = []
            self._own_dir = ""
            self.path = ""
            return self

        own = dirs[-1]  # _active_folder_dirs always puts the active folder last
        entries, owners = [], []
        for folder_dir in dirs:
            backend = self._backend(folder_dir)
            if not core.storage.TEMPORARY:
                backend.load()
            for mem in backend:
                if isinstance(mem, dict):
                    entries.append(mem)
                    owners.append(folder_dir)

        self.clear()
        list.extend(self, entries)
        self._owners = owners
        self._loaded_dirs = dirs
        self._own_dir = own
        self.path = os.path.join(own, FOLDER_FILE)
        return self

    def save(self):
        groups = {}
        for mem, folder_dir in zip(list(self), self._owners):
            groups.setdefault(folder_dir, []).append(mem)

        for folder_dir in self._loaded_dirs:
            backend = self._backend(folder_dir)
            backend.clear()
            backend.extend(groups.get(folder_dir, []))
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
        """ranked text search across every active folder"""
        self.load()
        return await core.search.search(list(self), query, field_weights=field_weights, top_n=top_n)

    # -- extras used by this module --------------------------------------

    def folder_counts(self):
        """returns {folder relative path: entry count} for the folders in this view"""
        counts = {}
        for folder_dir in self._loaded_dirs:
            rel = self.module._rel(folder_dir)
            counts[rel] = sum(1 for d in self._owners if d == folder_dir)
        return counts

    def breakdown(self):
        """human-readable per-folder breakdown of this view"""
        parts = []
        for folder_dir in self._loaded_dirs:
            rel = self.module._rel(folder_dir)
            count = sum(1 for d in self._owners if d == folder_dir)
            marker = "  <- where new memories are saved" if folder_dir == self._own_dir else ""
            parts.append(f"  {rel}: {count} memories{marker}")
        return "\n".join(parts)


class MemoryFolders(core.module.Module):
    """Augments the memory module with a directory tree of memory folders: create folders inside folders, then activate any folder to instantly switch which memories (its own plus all its sub-folders' ones) are active and available.

    Each memory folder is a directory holding its own memory file, with the 'root' folder as the base of the tree. Activating a folder makes its memories and all memories of folders nested inside it active; new memories are saved into the active folder itself. The default memory tools (create, edit, search, ...) keep working — they simply operate on the active folder subtree. The user's existing memories are migrated into the root folder automatically on first run."""

    category = "memory"

    settings = {
        "folders_folder": {
            "type": "string",
            "default": "memory_folders",
            "description": "Folder inside OpenLumara's data directory that holds the memory folder tree. The 'root' folder inside it is the base of the tree.",
        },
        "show_active_folder_prompt": {
            "default": True,
            "description": "Tell the AI which memory folder is currently active at the end of the context, so it always knows where its memories live and where new ones are saved.",
        },
    }

    # -------------------------
    #   LIFECYCLE
    # -------------------------

    async def on_ready(self):
        self._view = None
        self._folders_root = None
        self._active_text_obj = None

        self._setup()
        self._view = FolderView(self)
        self._attach()

        if "memory" not in self.manager.modules:
            self.log(self.name, "WARNING: the memory module is not enabled — memory folders will have no effect until it is.")

        self.log(self.name, f"memory folders ready (active: {self._active_path()}, tree root: {self._folders_root})")

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
        if not self.config.get("show_active_folder_prompt"):
            return None

        # prompt-cache optimization: this message is rebuilt at the end of the context on
        # every request, so it must stay byte-identical between folder switches. memory
        # counts and per-folder breakdowns are deliberately NOT included — they change on
        # every memory write and would break prefix cache matches. counts are available
        # on demand via list_folders.
        active = self._active_path()
        return (
            f"Memory folders are active: the currently active folder is '{active}'. "
            f"New memories are saved to it, and the memories available to your memory tools are those of '{active}' plus all folders nested inside it. "
            f"Switch or create folders with the memory folder tools or the /memory-folder command."
        )

    # -------------------------
    #   AI TOOLS
    # -------------------------

    @core.module.tool
    async def list_folders(self):
        """Lists every memory folder directory as a tree, with memory counts and the active folder marked.

        Returns:
            a tree of all folders: own memory count and total count including sub-folders
        """
        self._setup()
        folders = self._discover()
        if not folders:
            return self.result("no memory folders found (the root folder is missing!)", success=False)

        counts = {d: len(self._read_folder(d)) for d in folders}
        active_path = self._active_path()
        active_dir = self._safe_folder_dir(active_path)

        lines = ["memory folders (path — memories here / total in subtree):"]
        for d in folders:
            rel = self._rel(d)
            depth = rel.count("/")
            subtree = sum(c for o, c in counts.items() if o == d or o.startswith(d + os.sep))
            mark = "  [ACTIVE]" if d == active_dir else ""
            lines.append(f"{'  ' * depth}{rel} — {counts[d]} / {subtree}{mark}")

        return self.result("\n".join(lines))

    @core.module.tool
    async def create_folder(self, parent: str, name: str):
        """Creates a new memory folder directory inside an existing memory folder.

        Args:
            parent: path of the existing folder that will contain the new one (e.g. 'root' or 'root/work')
            name: name of the new folder directory (e.g. 'work'); letters, numbers, spaces, dashes, underscores and dots are allowed
        """
        try:
            parts = self._parse_path(parent)
            parent_dir = self._folder_dir(parts)
        except ValueError as e:
            return self.result(str(e), success=False)

        name = str(name or "").strip()
        if not _valid_name(name):
            return self.result(f"invalid folder name '{name}' — must start with a letter or number and may contain letters, numbers, spaces, dashes, underscores and dots", success=False)

        if not self._is_folder(parent_dir):
            return self.result(f"parent folder '{'/'.join(parts)}' does not exist — use list_folders to see the tree", success=False)

        child = os.path.join(parent_dir, name)
        if os.path.exists(child):
            return self.result(f"a directory '{name}' already exists inside '{'/'.join(parts)}'", success=False)

        if core.storage.TEMPORARY:
            return self.result("folder creation is disabled while running in temporary mode", success=False)

        os.makedirs(child, exist_ok=False)
        core.storage.StorageList("memory", type="msgpack", path=child, autoload=False)  # creates the empty memory.mp

        self._refresh()
        new_path = "/".join(parts + [name])
        return self.result(f"created memory folder '{new_path}' (empty). Activate it with activate_folder('{new_path}') to start saving memories to it.")

    @core.module.tool
    async def activate_folder(self, path: str):
        """Switches which memory folder is active. All memories of that folder and of every folder nested inside it become active and available; new memories are saved into the activated folder itself.

        Args:
            path: the folder to activate (e.g. 'root', 'root/work' or just 'work' — paths are relative to the root folder)
        """
        try:
            parts = self._parse_path(path)
            folder_dir = self._folder_dir(parts)
        except ValueError as e:
            return self.result(str(e), success=False)

        if not self._is_folder(folder_dir):
            return self.result(f"memory folder '{'/'.join(parts)}' doesn't exist — use list_folders to see the tree", success=False)

        self._active_text().set("/".join(parts))
        self._refresh()

        active = self._active_path()
        total = len(self._view)
        breakdown = self._view.breakdown()
        return self.result(f"active memory folder: '{active}' — {total} memories active:\n{breakdown}")

    @core.module.tool
    async def delete_folder(self, path: str, force: bool = False):
        """Deletes a memory folder directory and every folder nested inside it. DANGEROUS: memories are removed from disk.

        Args:
            path: the folder to delete (the 'root' folder cannot be deleted)
            force: set to True to also delete when the folders still contain memories
        """
        try:
            parts = self._parse_path(path)
            folder_dir = self._folder_dir(parts)
        except ValueError as e:
            return self.result(str(e), success=False)

        if parts == [ROOT_FOLDER]:
            return self.result("the root folder cannot be deleted", success=False)

        if not self._is_folder(folder_dir):
            return self.result(f"memory folder '{'/'.join(parts)}' doesn't exist", success=False)

        if core.storage.TEMPORARY:
            return self.result("folder deletion is disabled while running in temporary mode", success=False)

        subtree = [d for d in self._discover() if d == folder_dir or d.startswith(folder_dir + os.sep)]
        counts = {self._rel(d): len(self._read_folder(d)) for d in subtree}
        total = sum(counts.values())

        if total and not force:
            detail = ", ".join(f"{k}: {v}" for k, v in counts.items() if v)
            return self.result(f"refusing to delete: {total} memories would be lost ({detail}). Pass force=True to delete anyway.", success=False)

        # if the active folder lives inside the doomed subtree, fall back to root first
        active_path = self._active_path()
        active_dir = self._safe_folder_dir(active_path)
        if active_dir and (active_dir == folder_dir or active_dir.startswith(folder_dir + os.sep)):
            self._active_text().set(ROOT_FOLDER)

        shutil.rmtree(folder_dir)

        self._refresh()
        return self.result(f"deleted memory folder '{'/'.join(parts)}' ({total} memories removed across {len(subtree)} folder(s)). Active folder: '{self._active_path()}'")

    # -- AI GENERATED CODE (Qwen3.8 Flash Next) :: (2026-10-24)
    # webui extension routes for the memory folder sidebar panel. Private
    # methods are ignored by the tool loader; @webui.route exposes them under
    # /api/ext/memory-folders/<path>.

    @webui.route("tree")
    async def _route_tree(self, body=None, query=None):
        """folder tree for the sidebar panel"""
        self._setup()
        folders = self._discover()
        counts = {d: len(self._read_folder(d)) for d in folders}

        active_dir = self._safe_folder_dir(self._active_path())
        if active_dir not in counts:
            active_dir = os.path.join(self._folders_root, ROOT_FOLDER)

        items = []
        for folder_dir in folders:
            rel = self._rel(folder_dir)
            items.append({
                "path": rel,
                "name": rel.rsplit("/", 1)[-1],
                "depth": rel.count("/"),
                "own": counts[folder_dir],
                "subtree": sum(c for o, c in counts.items() if o == folder_dir or o.startswith(folder_dir + os.sep)),
                "active": folder_dir == active_dir,
            })

        active_total = sum(c for o, c in counts.items() if o == active_dir or o.startswith(active_dir + os.sep))
        return {"active": self._rel(active_dir), "total_active": active_total, "folders": items}

    @webui.route("activate", method="POST")
    async def _route_activate(self, body=None, query=None):
        path = str((body or {}).get("path", "")).strip()
        if not path:
            return self.result("no memory folder path given", success=False)
        return await self.activate_folder(path)

    @webui.route("create", method="POST")
    async def _route_create(self, body=None, query=None):
        body = body or {}
        parent = str(body.get("parent", "")).strip()
        name = str(body.get("name", "")).strip()
        if not parent or not name:
            return self.result("both a parent folder and a name are required", success=False)
        return await self.create_folder(parent, name)

    @webui.route("delete", method="POST")
    async def _route_delete(self, body=None, query=None):
        body = body or {}
        path = str(body.get("path", "")).strip()
        if not path:
            return self.result("no memory folder path given", success=False)
        return await self.delete_folder(path, force=bool(body.get("force")))

    # -------------------------
    #   USER-FACING COMMANDS
    # -------------------------

    @core.module.command("memory-folder", help={
        "": "Lists all memory folders and marks the active one",
        "activate <path>": "Switch the active memory folder, e.g. '/memory-folder activate root/work'",
        "create <parent> <name>": "Create a folder inside an existing one, e.g. '/memory-folder create root work'",
        "delete <path> [force]": "Delete a folder and its sub-folders, e.g. '/memory-folder delete work force'",
    })
    async def memory_folder_command(self, args: list):
        args = [str(a) for a in (args or [])]
        if not args:
            return (await self.list_folders())["content"]

        sub = args[0].lower()
        if sub == "activate" and len(args) >= 2:
            return (await self.activate_folder(" ".join(args[1:])))["content"]
        if sub == "create" and len(args) >= 3:
            return (await self.create_folder(" ".join(args[1:-1]), args[-1]))["content"]
        if sub == "delete" and len(args) >= 2:
            force = args[-1].lower() == "force"
            path_args = args[1:-1] if force else args[1:]
            if not path_args:
                return "usage: /memory-folder delete <path> [force]"
            return (await self.delete_folder(" ".join(path_args), force))["content"]

        return "usage: /memory-folder [activate <path> | create <parent> <name> | delete <path> [force]] (no args lists all folders)"

    # -------------------------
    #   INTERNALS
    # -------------------------

    def _setup(self):
        """ensure the folders tree exists; migrate the default memory folder into root once"""
        root = self._folders_root_path()
        if self._folders_root and self._folders_root != root:
            self._active_text_obj = None
            if self._view is not None:
                self._view.invalidate()
        self._folders_root = root

        if core.storage.TEMPORARY:
            return

        root_dir = os.path.join(root, ROOT_FOLDER)
        os.makedirs(root_dir, exist_ok=True)
        root_file = os.path.join(root_dir, FOLDER_FILE)
        default_file = os.path.join(core.get_data_path(), "memory.mp")

        if not os.path.exists(root_file):
            if os.path.exists(default_file):
                # one-time migration: the memory module's default folder becomes the root folder
                shutil.move(default_file, root_file)
                self.log(self.name, "migrated the default memory folder into the root folder")
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
                self.log(self.name, f"merged {added} memories created while memory-folders was disabled into the root folder")
        except Exception as e:
            self.log(self.name, f"could not merge leftover default memory folder: {core.detail_error(e)}")

    def _folders_root_path(self):
        folder = str(self.config.get("folders_folder") or "memory_folders").strip().strip("/\\")
        parts = [p for p in folder.replace("\\", "/").split("/") if p not in ("", ".", "..")]
        if not parts or any(not _valid_name(p) for p in parts):
            parts = ["memory_folders"]
        return os.path.join(core.get_data_path(), *parts)

    def _parse_path(self, path):
        """turns 'work' or 'root/work/projects' into ['root','work','projects']; raises ValueError on junk"""
        raw = str(path or "").strip().replace("\\", "/")
        parts = [p for p in raw.split("/") if p not in ("", ".")]
        if not parts:
            raise ValueError("no memory folder path given")
        for p in parts:
            if not _valid_name(p):
                raise ValueError(f"invalid folder name '{p}' — letters, numbers, spaces, dashes, underscores and dots are allowed")
        if parts[0] != ROOT_FOLDER:
            parts.insert(0, ROOT_FOLDER)  # bare names like 'work' live under root
        return parts

    def _folder_dir(self, parts):
        d = os.path.join(self._folders_root, *parts)
        base = os.path.realpath(self._folders_root)
        real = os.path.realpath(d)
        if real != base and not real.startswith(base + os.sep):
            raise ValueError("folder path escapes the memory folders folder")
        return d

    def _safe_folder_dir(self, path):
        try:
            return self._folder_dir(self._parse_path(path))
        except ValueError:
            return None

    def _rel(self, folder_dir):
        return os.path.relpath(folder_dir, self._folders_root).replace(os.sep, "/")

    def _is_folder(self, folder_dir):
        return os.path.isfile(os.path.join(folder_dir, FOLDER_FILE))

    def _read_folder(self, folder_dir):
        backend = core.storage.StorageList("memory", type="msgpack", path=folder_dir, autoload=False)
        if not core.storage.TEMPORARY:
            backend.load()
        return list(backend)

    def _discover(self):
        """all folder directories, root first, then nested folders alphabetically (depth-first)"""
        found = []

        def walk(directory):
            found.append(directory)
            try:
                entries = sorted(os.listdir(directory), key=str.lower)
            except OSError:
                return
            for entry in entries:
                sub = os.path.join(directory, entry)
                if os.path.isdir(sub) and self._is_folder(sub):
                    walk(sub)

        root_dir = os.path.join(self._folders_root, ROOT_FOLDER)
        if self._is_folder(root_dir):
            walk(root_dir)
        return found

    def _active_text(self):
        if self._active_text_obj is None:
            self._active_text_obj = core.storage.StorageText("active_folder", path=self._folders_root)
        return self._active_text_obj

    def _active_folder_parts(self):
        try:
            return self._parse_path(self._active_text().get())
        except ValueError:
            return [ROOT_FOLDER]

    def _active_path(self):
        return "/".join(self._active_folder_parts())

    def _active_own_dir(self):
        d = self._safe_folder_dir(self._active_path())
        return d if d and self._is_folder(d) else os.path.join(self._folders_root, ROOT_FOLDER)

    def _active_folder_dirs(self):
        """directories backing the view: [sub-folders...] [own folder last]"""
        if self._folders_root is None:
            self._setup()

        own = self._active_own_dir()
        all_folders = self._discover()
        if own not in all_folders:
            own = os.path.join(self._folders_root, ROOT_FOLDER)

        dirs = [d for d in all_folders if d != own and d.startswith(own + os.sep)]
        dirs.append(own)
        return dirs

    def _refresh(self):
        """rebuild the view after the tree or active folder changed, and make sure it's attached"""
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
            self.log(self.name, "attached memory folder view to the memory module")
        return mem
