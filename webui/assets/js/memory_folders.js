/*
 * memory-folders — memory folder sidebar panel logic
 * Copyright (C) 2026 theunknownmuncher <theunknownmuncher@protonmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

/* -- AI GENERATED CODE (Qwen3.8 Flash Next) :: (2026-10-24)
   memory folder sidebar panel logic. The plain global object is registered as
   the Alpine state memoryFolders, used by the sidebar tab through
   memoryFoldersComponent(). Talks to /api/ext/memory-folders/. */
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

    async refresh() {
        this.loading = true;
        this.error = "";

        try {
            const data = await simpleApiFetch("/api/ext/memory-folders/tree") || {};
            this.folders = data.folders || [];
            this.active = data.active || "";
            this.totalActive = data.total_active || 0;
            this.loaded = true;
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
