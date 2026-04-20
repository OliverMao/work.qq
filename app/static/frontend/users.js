import { createApp } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import {
  listUserBindings,
  createUserBinding,
  updateUserBinding,
  deleteUserBinding,
} from "/static/frontend/api.js";

createApp({
  data() {
    return {
      keyword: "",
      keywordInput: "",
      userForm: {
        user_id: "",
        nickname: "",
      },
      userBindings: [],
      userEditMap: {},
      loading: {
        list: false,
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
  mounted() {
    this.refreshUserBindings();
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
