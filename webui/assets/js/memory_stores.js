/*
 * memory-folders — memory folder sidebar panel logic
 * Copyright (C) 2026 theunknownmuncher <theunknownmuncher@protonmail.com>
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

/* -- AI GENERATED CODE (Qwen3.8 Flash Next) :: (2026-10-24)
   memory store sidebar panel logic. The plain global object is registered as
   the Alpine store memoryStores, used by the sidebar tab through
   memoryStoresComponent(). Talks to /api/ext/memory-folders/. */
const MEMORY_STORES_PANEL = {
    stores: [],
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
            this.stores = data.stores || [];
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
            const msg = await simpleApiPost("/api/ext/memory-folders/activate", { path });
            this.notice = typeof msg === "string" ? msg.split("\n")[0] : "store activated";
            await this.refresh();
            this.refreshMemoryPanel();
        } catch (e) {
            this.error = this.errorText(e);
        }
    },

    openCreate(store) {
        this.creatingParent = store.path;
        this.newName = "";
        this.error = "";
        this.notice = "";
        Alpine.store("ui").openModal("memory_store_create");
    },

    cancelCreate() {
        this.newName = "";
        this.error = "";
        Alpine.store("ui").closeModal();
    },

    async create() {
        const name = this.newName.trim();
        if (!name) {
            this.error = "give the new store a name first";
            return;
        }

        this.creating = true;
        this.error = "";
        this.notice = "";

        try {
            const msg = await simpleApiPost("/api/ext/memory-folders/create", { parent: this.creatingParent, name });
            this.notice = typeof msg === "string" ? msg.split("\n")[0] : "store created";
            this.newName = "";
            await this.refresh();
            Alpine.store("ui").closeModal();
        } catch (e) {
            this.error = this.errorText(e);
        } finally {
            this.creating = false;
        }
    },

    async remove(store) {
        if (store.path === "root") {
            return;
        }

        const warning = store.subtree > 0
            ? `Delete memory store '${store.path}' and its ${store.subtree} memories (including sub-stores)?\n\nThis cannot be undone.`
            : `Delete memory store '${store.path}'?\n\nThis cannot be undone.`;

        if (!window.confirm(warning)) {
            return;
        }

        this.error = "";
        this.notice = "";

        try {
            await simpleApiPost("/api/ext/memory-folders/delete", { path: store.path, force: false });
            this.notice = `deleted '${store.path}'`;
            await this.refresh();
            this.refreshMemoryPanel();
        } catch (e) {
            const text = this.errorText(e);

            // the backend refuses non-empty stores without force — offer a second, explicit
            // confirmation. "Pass force=True to delete anyway." is guidance for the AI tool,
            // so it is stripped from the human-facing dialog.
            if (text.startsWith("refusing to delete")) {
                const friendly = text.replace(/\s*Pass force=True to delete anyway\.?/, "");
                if (window.confirm(friendly + "\n\nDelete anyway?")) {
                    try {
                        await simpleApiPost("/api/ext/memory-folders/delete", { path: store.path, force: true });
                        this.notice = `deleted '${store.path}'`;
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
        // switching stores immediately shows the new store's memories. resetting
        // loadedTags re-fetches the tag list too (tags differ per store).
        try {
            const panel =
                (window.Alpine && Alpine.store("memoryPanel")) ||
                (typeof MEMORY_PANEL !== "undefined" ? MEMORY_PANEL : null);

            if (panel && typeof panel.refresh === "function") {
                panel.loadedTags = false;
                panel.refresh(true);
            }

            window.dispatchEvent(new CustomEvent("memory-stores-changed"));
        } catch (e) {
            // memory panel extension not loaded (memory module or its webui extension disabled)
        }
    },

    indent(store) {
        return { paddingLeft: (6 + store.depth * 14) + "px" };
    },

    errorText(e) {
        if (e && typeof e === "object") {
            return e.message || JSON.stringify(e);
        }
        return String(e);
    }
};

document.addEventListener("alpine:init", () => {
    Alpine.store("memoryStores", MEMORY_STORES_PANEL);
});

function memoryStoresComponent() {
    return Alpine.store("memoryStores") || MEMORY_STORES_PANEL;
}
