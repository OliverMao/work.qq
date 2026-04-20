import { createApp } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import {
  listArchiveUserCandidates,
  autoBindUserNicknames,
  querySingleUserNickname,
  createUserBinding,
  updateUserBinding,
} from "/static/frontend/api.js";

createApp({
  data() {
    return {
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
      bindingDialog: {
        visible: false,
        user_id: "",
        nickname: "",
        is_bound: false,
      },
      userCandidates: [],
      loading: {
        candidates: false,
        autoBind: false,
        queryOneId: "",
        bindingSave: false,
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
    bindingButtonText(item) {
      return `修改（${item.is_bound ? "已绑定" : "未绑定"}）`;
    },
    openBindingDialog(item) {
      this.bindingDialog = {
        visible: true,
        user_id: item.user_id || "",
        nickname: item.nickname || "",
        is_bound: Boolean(item.is_bound),
      };
    },
    closeBindingDialog() {
      if (this.loading.bindingSave) {
        return;
      }
      this.bindingDialog.visible = false;
    },
    async saveBindingFromDialog() {
      if (this.loading.bindingSave) {
        return;
      }

      const userId = String(this.bindingDialog.user_id || "").trim();
      const nickname = String(this.bindingDialog.nickname || "").trim();
      if (!userId || !nickname) {
        this.setMessage("user_id 和昵称不能为空", "warn");
        return;
      }

      this.loading.bindingSave = true;
      this.clearMessage();
      try {
        if (this.bindingDialog.is_bound) {
          await updateUserBinding(userId, nickname);
        } else {
          await createUserBinding(userId, nickname);
        }
        this.setMessage(`绑定保存成功：${userId} -> ${nickname}`, "ok");
        this.bindingDialog.visible = false;
        await this.refreshUserCandidates();
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.bindingSave = false;
      }
    },
    async queryOneCandidate(item) {
      const userId = String(item.user_id || "").trim();
      if (!userId) {
        this.setMessage("user_id 为空，无法查询", "warn");
        return;
      }

      this.loading.queryOneId = userId;
      this.clearMessage();
      try {
        const data = await querySingleUserNickname(userId);
        const userTypeText = data.user_type === "external" ? "外部用户" : "内部用户";
        const actionText = this.formatAction(data.action);
        this.setMessage(
          `查询完成：${userId} -> ${data.nickname || "-"}（${userTypeText}，${data.query_api || "-"}，${actionText}）`,
          "ok",
        );
        await this.refreshUserCandidates();
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.queryOneId = "";
      }
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

        await this.refreshUserCandidates();
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.autoBind = false;
      }
    },
  },
}).mount("#app");
