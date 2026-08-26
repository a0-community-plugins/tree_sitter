import { createStore } from "/js/AlpineStore.js";
import * as api from "/js/api.js";
import {
  toastFrontendError,
  toastFrontendSuccess,
  toastFrontendInfo,
} from "/components/notifications/notification-store.js";

export const store = createStore("treeSitterInspector", {
  filePath: "",
  rootPath: "",
  language: "",
  query: "",
  task: "",
  symbol: "",
  busy: "",
  runtime: null,
  inspection: null,
  indexStatus: null,
  searchResult: null,
  contextResult: null,

  async onOpen() {
    this.inspection = null;
    this.searchResult = null;
    this.contextResult = null;
    await this.refreshRuntime();
  },

  cleanup() {},

  async refreshRuntime() {
    try {
      this.runtime = await api.callJsonApi("/plugins/tree_sitter/runtime_status", {});
      if (!this.runtime.ready) {
        void toastFrontendInfo("Install or update the plugin to provision its pinned runtime.", "Tree-sitter");
      }
    } catch (error) {
      this.fail(error);
    }
  },

  async inspectFile() {
    if (!this.filePath) return this.fail(new Error("Enter a file path to inspect."));
    await this.run("inspect", async () => {
      this.inspection = await api.callJsonApi("/plugins/tree_sitter/inspect", {
        path: this.filePath,
        root_path: this.rootPath || undefined,
        language: this.language || undefined,
        query: this.query || undefined,
      });
    });
  },

  async reindex(force = false) {
    if (!this.rootPath) return this.fail(new Error("Enter a repository root."));
    await this.run("index", async () => {
      this.indexStatus = await api.callJsonApi("/plugins/tree_sitter/reindex", {
        root_path: this.rootPath,
        force,
      });
      void toastFrontendSuccess(
        `Indexed ${this.indexStatus.file_count || 0} files; ${this.indexStatus.changed_files || 0} changed.`,
        "Tree-sitter",
      );
    });
  },

  async refreshIndexStatus() {
    if (!this.rootPath) return this.fail(new Error("Enter a repository root."));
    await this.run("status", async () => {
      const response = await api.callJsonApi("/plugins/tree_sitter/index_status", { root_path: this.rootPath });
      this.indexStatus = response.status;
    });
  },

  async search() {
    if (!this.rootPath || !this.symbol) return this.fail(new Error("Enter a repository root and symbol."));
    await this.run("search", async () => {
      this.searchResult = await api.callJsonApi("/plugins/tree_sitter/search", {
        root_path: this.rootPath,
        query: this.symbol,
      });
    });
  },

  async buildContext() {
    if (!this.rootPath || !this.task) return this.fail(new Error("Enter a repository root and coding task."));
    await this.run("context", async () => {
      this.contextResult = await api.callJsonApi("/plugins/tree_sitter/context", {
        root_path: this.rootPath,
        task: this.task,
        symbol: this.symbol || undefined,
      });
    });
  },

  async run(name, operation) {
    this.busy = name;
    try {
      await operation();
    } catch (error) {
      this.fail(error);
    } finally {
      this.busy = "";
    }
  },

  fail(error) {
    void toastFrontendError(error instanceof Error ? error.message : String(error), "Tree-sitter");
  },

  formatJson(value) {
    return value ? JSON.stringify(value, null, 2) : "";
  },
});
