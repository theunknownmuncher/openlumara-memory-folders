/*
 * memory-folders — memory folder sidebar panel logic
 * Copyright (C) 2026 theunknownmuncher <theunknownmuncher@protonmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

/* -- AI GENERATED CODE (Qwen3.8 Flash Next) :: (2026-10-24)
   memory folder sidebar panel logic. The plain global object is registered as
   the Alpine state memoryFolders, used by the sidebar tab through
   memoryFoldersComponent(). Talks to /api/ext/memory-folders/. */

/* -- AI GENERATED CODE (Qwen3.8 Flash Next) :: (2026-10-27)
   revamped into a filesystem-style manager: the folder tree on top browses
   folders, the memory browser below lists the selected folder's own memories
   like files. Memories support view (browse + filter), edit (modal), delete,
   copy/cut + paste (clipboard with copy/move semantics) and move between
   folders. */
const MEMORY_FOLDERS_PANEL = {
    folders: [],
    active: "",
    totalActive: 0,
    loading: false,
    loaded: false,
    error: "",
    notice: "",
    creatingParent: "root",
    newName: "",
    creating: false,

    // memory browser (the folder currently being browsed, like a file manager)
    selected: "",
    memPath: "",
    memories: [],
    memTotal: 0,
    memLoading: false,
    memFilter: "",

    // filesystem clipboard: { mode: "copy" | "move", from: folder path, item: memory }
    clipboard: null,

    // memory edit modal (shares this store, modal: memory_folder_memory_edit)
    editId: "",
    editContent: "",
    editTags: "",
    editPinned: false,
    savingEdit: false,

    async refresh() {
        this.loading = true;
        this.error = "";

        try {
            const data = await simpleApiFetch("/api/ext/memory-folders/tree") || {};
            this.folders = data.folders || [];
            this.active = data.active || "";
            this.totalActive = data.total_active || 0;
            this.loaded = true;

            // keep browsing the selected folder while it exists; otherwise fall
            // back to the active folder (first load) or clear the browser
            if (!this.folders.some(f => f.path === this.selected)) {
                this.selected = this.folders.some(f => f.path === this.active) ? this.active : "";
            }

            if (this.selected) {
                await this.loadMemories();
            } else {
                this.memories = [];
                this.memTotal = 0;
                this.memPath = "";
            }
        } catch (e) {
            this.error = this.errorText(e);
        } finally {
            this.loading = false;
        }
    },

    async activate(path) {
        if (path === this.active) {
            return;
        }

        this.error = "";
        this.notice = "";

        try {
            await simpleApiPost("/api/ext/memory-folders/activate", { path });
            await this.refresh();
            this.notice = `activated '${path}' — ${this.totalActive} memories`;
            this.refreshMemoryPanel();
        } catch (e) {
            this.error = this.errorText(e);
        }
    },

    // -- folder CRUD ----------------------------------------------------

    openCreate(folder) {
        this.creatingParent = folder.path;
        this.newName = "";
        this.error = "";
        this.notice = "";
        Alpine.store("ui").openModal("memory_folder_create");
    },

    cancelCreate() {
        this.newName = "";
        this.error = "";
        Alpine.store("ui").closeModal();
    },

    async create() {
        const name = this.newName.trim();
        if (!name) {
            this.error = "give the new folder a name first";
            return;
        }

        this.creating = true;
        this.error = "";
        this.notice = "";

        try {
            await simpleApiPost("/api/ext/memory-folders/create", { parent: this.creatingParent, name });
            this.newName = "";
            await this.refresh();
            Alpine.store("ui").closeModal();
            this.notice = `created folder '${this.creatingParent}/${name}'`;
        } catch (e) {
            this.error = this.errorText(e);
        } finally {
            this.creating = false;
        }
    },

    async remove(folder) {
        if (folder.path === "root") {
            return;
        }

        const warning = folder.subtree > 0
            ? `Delete memory folder '${folder.path}' and its ${folder.subtree} memories (including sub-folders)?\n\nThis cannot be undone.`
            : `Delete memory folder '${folder.path}'?\n\nThis cannot be undone.`;

        if (!window.confirm(warning)) {
            return;
        }

        this.error = "";
        this.notice = "";

        try {
            await simpleApiPost("/api/ext/memory-folders/delete", { path: folder.path, force: false });
            this.notice = `deleted '${folder.path}'`;
            await this.refresh();
            this.refreshMemoryPanel();
        } catch (e) {
            const text = this.errorText(e);

            // The backend refuses non-empty folders without force. That sentence
            // is tool guidance, so strip it from the human-facing second dialog.
            if (text.startsWith("refusing to delete")) {
                const friendly = text.replace(/\s*Pass force=True to delete anyway\.?/, "");
                if (window.confirm(friendly + "\n\nDelete anyway?")) {
                    try {
                        await simpleApiPost("/api/ext/memory-folders/delete", { path: folder.path, force: true });
                        this.notice = `deleted '${folder.path}'`;
                        await this.refresh();
                        this.refreshMemoryPanel();
                    } catch (e2) {
                        this.error = this.errorText(e2);
                    }
                }
            } else {
                this.error = text;
            }
        }
    },

    // -- memory browser (the selected folder's own memories) ------------

    async select(folder) {
        this.selected = folder.path;
        this.error = "";
        this.notice = "";
        this.memFilter = "";
        await this.loadMemories();
    },

    async loadMemories() {
        if (!this.selected) {
            this.memories = [];
            this.memTotal = 0;
            this.memPath = "";
            return;
        }

        this.memLoading = true;

        try {
            const params = new URLSearchParams({ path: this.selected, limit: "200" });
            const data = await simpleApiFetch("/api/ext/memory-folders/memories?" + params.toString()) || {};
            this.memories = data.items || [];
            this.memTotal = data.total || 0;
            this.memPath = data.path || this.selected;
        } catch (e) {
            this.error = this.errorText(e);
            this.memories = [];
            this.memTotal = 0;
        } finally {
            this.memLoading = false;
        }
    },

    visibleMemories() {
        const q = this.memFilter.trim().toLowerCase();
        if (!q) {
            return this.memories;
        }

        return this.memories.filter(item =>
            (item.content || "").toLowerCase().includes(q) ||
            (item.tags || []).some(tag => String(tag).toLowerCase().includes(q))
        );
    },

    isOnClipboard(item) {
        return !!this.clipboard
            && this.clipboard.from === this.memPath
            && this.clipboard.item.id === item.id;
    },

    // -- filesystem clipboard: copy / cut / paste (== copy & move) -------

    copyMemory(item) {
        this.clipboard = { mode: "copy", from: this.memPath, item };
        this.error = "";
        this.notice = "memory copied — open a folder and paste it there";
    },

    cutMemory(item) {
        this.clipboard = { mode: "move", from: this.memPath, item };
        this.error = "";
        this.notice = "memory cut — open a folder and paste it there";
    },

    clearClipboard() {
        this.clipboard = null;
    },

    canPasteInto(path) {
        if (!this.clipboard || !path) {
            return false;
        }
        return this.clipboard.mode === "copy" || this.clipboard.from !== path;
    },

    async pasteInto(path) {
        if (!this.canPasteInto(path)) {
            return;
        }

        const { mode, from, item } = this.clipboard;
        this.error = "";
        this.notice = "";

        try {
            const endpoint = mode === "copy" ? "copy_memory" : "move_memory";
            await simpleApiPost(`/api/ext/memory-folders/${endpoint}`, { id: item.id, from, to: path });

            this.clipboard = null;
            await this.refresh();
            this.refreshMemoryPanel();
            this.notice = mode === "copy"
                ? `memory copied into '${path}'`
                : `memory moved from '${from}' to '${path}'`;
        } catch (e) {
            this.error = this.errorText(e);
        }
    },

    // -- memory edit / delete --------------------------------------------

    openEdit(item) {
        this.editId = item.id;
        this.editContent = item.content || "";
        this.editTags = (Array.isArray(item.tags) ? item.tags : []).join(", ");
        this.editPinned = !!item.pinned;
        this.savingEdit = false;
        this.error = "";
        Alpine.store("ui").openModal("memory_folder_memory_edit");
    },

    closeEdit() {
        this.editId = "";
        this.editContent = "";
        this.editTags = "";
        this.editPinned = false;
        this.savingEdit = false;
        this.error = "";
        Alpine.store("ui").closeModal();
    },

    async saveEdit() {
        if (!this.editId || this.savingEdit) {
            return;
        }

        const content = this.editContent.trim();
        if (!content) {
            this.error = "memory content cannot be empty";
            return;
        }

        const tags = this.editTags
            .split(",")
            .map(tag => tag.trim())
            .filter(tag => tag.length > 0);

        this.savingEdit = true;
        this.error = "";

        try {
            await simpleApiPost("/api/ext/memory-folders/update_memory", {
                path: this.memPath,
                id: this.editId,
                content: content,
                tags: tags,
                pinned: this.editPinned,
            });

            await this.loadMemories();
            this.closeEdit();
            this.notice = "memory updated";
            this.refreshMemoryPanel();
        } catch (e) {
            this.error = this.errorText(e);
        } finally {
            this.savingEdit = false;
        }
    },

    async removeMemory(item) {
        const preview = (item.content || "").replace(/\s+/g, " ").trim().slice(0, 80);
        if (!window.confirm(`Delete this memory from '${this.memPath}'?\n\n"${preview}${(item.content || "").length > 80 ? ".." : ""}"\n\nThis cannot be undone.`)) {
            return;
        }

        this.error = "";
        this.notice = "";

        try {
            await simpleApiPost("/api/ext/memory-folders/delete_memory", { path: this.memPath, id: item.id });
            if (this.isOnClipboard(item)) {
                this.clearClipboard();
            }
            await this.refresh();
            this.refreshMemoryPanel();
            this.notice = "memory deleted";
        } catch (e) {
            this.error = this.errorText(e);
        }
    },

    // -- helpers -----------------------------------------------------------

    refreshMemoryPanel() {
        // the memory panel caches pinned/tags/search results; force a reload so
        // switching folders immediately shows the new folder's memories. resetting
        // loadedTags re-fetches the tag list too (tags differ per folder).
        try {
            const panel =
                (window.Alpine && Alpine.store("memoryPanel")) ||
                (typeof MEMORY_PANEL !== "undefined" ? MEMORY_PANEL : null);

            if (panel && typeof panel.refresh === "function") {
                panel.loadedTags = false;
                panel.refresh(true);
            }

            window.dispatchEvent(new CustomEvent("memory-folders-changed"));
        } catch (e) {
            // memory panel extension not loaded (memory module or its webui extension disabled)
        }
    },

    indent(folder) {
        return { paddingLeft: (6 + folder.depth * 14) + "px" };
    },

    formatDate(value) {
        if (!value) {
            return "";
        }

        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return String(value);
        }

        return date.toLocaleDateString();
    },

    errorText(e) {
        if (e && typeof e === "object") {
            return e.message || JSON.stringify(e);
        }
        return String(e);
    }
};

document.addEventListener("alpine:init", () => {
    Alpine.store("memoryFolders", MEMORY_FOLDERS_PANEL);
});

function memoryFoldersComponent() {
    return Alpine.store("memoryFolders") || MEMORY_FOLDERS_PANEL;
}
