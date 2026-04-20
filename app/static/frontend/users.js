import { createApp } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import {
  listUserBindings,
  listArchiveUserCandidates,
  autoBindUserNicknames,
  createUserBinding,
  updateUserBinding,
  deleteUserBinding,
} from "/static/frontend/api.js";

createApp({
  data() {
    return {
      keyword: "",
      keywordInput: "",
      candidateKeyword: "",
      candidateKeywordInput: "",
      candidateStats: {
        files_scanned: 0,
        messages_scanned: 0,
      },
      autoBindForm: {
        only_unbound: true,
        limit: 1000,
      },
      autoBindResult: null,
      userForm: {
        user_id: "",
        nickname: "",
      },
      userBindings: [],
      userCandidates: [],
      userEditMap: {},
      loading: {
        list: false,
        candidates: false,
        autoBind: false,
        create: false,
        updateId: "",
        deleteId: "",
      },
      message: {
        text: "",
        type: "ok",
      },
    };
  },
  computed: {
    autoQueryableCount() {
      return this.userCandidates.filter((item) => item.can_auto_query).length;
    },
    boundCandidateCount() {
      return this.userCandidates.filter((item) => item.is_bound).length;
    },
  },
  mounted() {
    this.refreshUserBindings();
    this.refreshUserCandidates();
  },
  methods: {
    setMessage(text, type = "ok") {
      this.message.text = text;
      this.message.type = type;
    },
    clearMessage() {
      this.message.text = "";
      this.message.type = "ok";
    },
    formatIsoTime(value) {
      if (!value) {
        return "-";
      }
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        return String(value);
      }
      return date.toLocaleString("zh-CN", { hour12: false });
    },
    syncUserEditMap() {
      const map = {};
      this.userBindings.forEach((item) => {
        map[item.user_id] = item.nickname || "";
      });
      this.userEditMap = map;
    },
    onUserNicknameEdit(userId, value) {
      this.userEditMap = {
        ...this.userEditMap,
        [userId]: value,
      };
    },
    normalizeLimit(value) {
      const n = Number(value);
      if (!Number.isFinite(n) || n < 1) {
        return 1000;
      }
      if (n > 10000) {
        return 10000;
      }
      return Math.floor(n);
    },
    formatAction(action) {
      if (action === "created") {
        return "新增";
      }
      if (action === "updated") {
        return "更新";
      }
      if (action === "unchanged") {
        return "不变";
      }
      return action || "-";
    },
    async refreshUserCandidates() {
      this.loading.candidates = true;
      try {
        const data = await listArchiveUserCandidates(this.candidateKeyword);
        this.userCandidates = data.items || [];
        this.candidateStats = {
          files_scanned: data.files_scanned || 0,
          messages_scanned: data.messages_scanned || 0,
        };
      } catch (err) {
        this.userCandidates = [];
        this.candidateStats = {
          files_scanned: 0,
          messages_scanned: 0,
        };
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.candidates = false;
      }
    },
    async applyCandidateFilter() {
      this.candidateKeyword = this.candidateKeywordInput.trim();
      await this.refreshUserCandidates();
    },
    async runAutoBind() {
      if (this.loading.autoBind) {
        return;
      }

      const limit = this.normalizeLimit(this.autoBindForm.limit);
      this.autoBindForm.limit = limit;

      const ok = window.confirm(
        `将自动查询并绑定昵称。\n仅绑定未绑定: ${this.autoBindForm.only_unbound ? "是" : "否"}\n最大处理数量: ${limit}`,
      );
      if (!ok) {
        return;
      }

      this.loading.autoBind = true;
      this.clearMessage();
      try {
        const data = await autoBindUserNicknames({
          keyword: this.candidateKeyword || null,
          only_unbound: this.autoBindForm.only_unbound,
          limit,
        });
        this.autoBindResult = data;

        const summary = [
          `处理 ${data.selected_user_ids || 0} 个`,
          `成功 ${data.success_count || 0} 个`,
          `失败 ${data.failed_count || 0} 个`,
        ].join("，");
        this.setMessage(`一键查询并绑定完成：${summary}`, "ok");

        await Promise.all([this.refreshUserBindings(), this.refreshUserCandidates()]);
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.autoBind = false;
      }
    },

    async refreshUserBindings() {
      this.loading.list = true;
      try {
        const data = await listUserBindings(this.keyword);
        this.userBindings = data.items || [];
        this.syncUserEditMap();
      } catch (err) {
        this.userBindings = [];
        this.userEditMap = {};
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.list = false;
      }
    },
    async applyFilter() {
      this.keyword = this.keywordInput.trim();
      await this.refreshUserBindings();
    },

    async createUserNickname() {
      const userId = this.userForm.user_id.trim();
      const nickname = this.userForm.nickname.trim();
      if (!userId || !nickname) {
        this.setMessage("user_id 和 昵称 不能为空", "warn");
        return;
      }

      this.loading.create = true;
      this.clearMessage();
      try {
        await createUserBinding(userId, nickname);
        this.userForm.user_id = "";
        this.userForm.nickname = "";
        this.setMessage(`用户昵称绑定已创建: ${userId}`, "ok");
        await this.refreshUserBindings();
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.create = false;
      }
    },

    async saveUserNickname(item) {
      const nickname = (this.userEditMap[item.user_id] || "").trim();
      if (!nickname) {
        this.setMessage("昵称不能为空", "warn");
        return;
      }

      this.loading.updateId = item.user_id;
      this.clearMessage();
      try {
        await updateUserBinding(item.user_id, nickname);
        this.setMessage(`用户昵称绑定已更新: ${item.user_id}`, "ok");
        await this.refreshUserBindings();
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.updateId = "";
      }
    },

    async removeUserBinding(item) {
      const ok = window.confirm(`确定删除用户昵称绑定?\nuser_id: ${item.user_id}`);
      if (!ok) {
        return;
      }

      this.loading.deleteId = item.user_id;
      this.clearMessage();
      try {
        await deleteUserBinding(item.user_id);
        this.setMessage(`用户昵称绑定已删除: ${item.user_id}`, "ok");
        await this.refreshUserBindings();
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.deleteId = "";
      }
    },
  },
}).mount("#app");
