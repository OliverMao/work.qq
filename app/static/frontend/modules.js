import { createApp } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import {
  listGroupModules,
  getGroupModule,
  createRoomBinding as apiCreateRoomBinding,
  updateRoomBinding as apiUpdateRoomBinding,
  deleteRoomBinding as apiDeleteRoomBinding,
  listUserBindings,
  createUserBinding as apiCreateUserBinding,
  updateUserBinding as apiUpdateUserBinding,
  deleteUserBinding as apiDeleteUserBinding,
} from "/static/frontend/api.js";

createApp({
  data() {
    return {
      modules: [],
      totalCount: 0,
      boundCount: 0,
      unboundCount: 0,
      keyword: "",
      keywordInput: "",
      editRoomNames: {},

      selectedModule: null,
      showViewer: false,
      selectedMessages: [],
      selectedCount: 0,
      selectedRawCount: 0,
      selectedLatestMsgtime: null,

      userKeyword: "",
      userKeywordInput: "",
      userForm: {
        user_id: "",
        nickname: "",
      },
      userBindings: [],
      userEditMap: {},

      loading: {
        modules: false,
        messages: false,
        roomBindingId: "",
        users: false,
        userCreate: false,
        userUpdateId: "",
        userDeleteId: "",
      },
      message: {
        text: "",
        type: "ok",
      },
    };
  },
  async mounted() {
    await Promise.all([this.refreshModules(), this.refreshUserBindings()]);
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
    formatUnixTime(value) {
      if (!value || Number(value) <= 0) {
        return "-";
      }
      const ts = Number(value);
      const date = new Date(ts >= 1000000000000 ? ts : ts * 1000);
      if (Number.isNaN(date.getTime())) {
        return String(value);
      }
      return date.toLocaleString("zh-CN", { hour12: false });
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
    normalizeTextContent(message) {
      const textPayload = message && message.text;
      const content = textPayload && textPayload.content;
      if (content === null || content === undefined) {
        return "";
      }
      return String(content);
    },
    toStructuredTextMessages(messages) {
      if (!Array.isArray(messages)) {
        return [];
      }

      return messages
        .filter((msg) => String((msg && msg.msgtype) || "").toLowerCase() === "text")
        .map((msg) => {
          const userId = String(msg.from || "");
          const display = String(msg.from_display || msg.from_nickname || msg.from || "");
          return {
            msgid: String(msg.msgid || ""),
            from_user_id: userId,
            from_display: display || userId,
            action: String(msg.action || ""),
            roomid: String(msg.roomid || ""),
            msgtype: String(msg.msgtype || ""),
            text_content: this.normalizeTextContent(msg),
          };
        });
    },

    buildRoomBindingCounts() {
      const bound = this.modules.filter((item) => !!item.room_name).length;
      this.boundCount = bound;
      this.unboundCount = this.modules.length - bound;
    },
    syncRoomEditMap() {
      const map = {};
      this.modules.forEach((item) => {
        map[item.roomid] = item.room_name || "";
      });
      this.editRoomNames = map;
    },
    onEditRoomName(roomid, value) {
      this.editRoomNames = {
        ...this.editRoomNames,
        [roomid]: value,
      };
    },

    async refreshModules() {
      this.loading.modules = true;
      try {
        const data = await listGroupModules(this.keyword);
        this.modules = data.items || [];
        this.totalCount = Number(data.count || 0);
        this.buildRoomBindingCounts();
        this.syncRoomEditMap();

        if (this.selectedModule) {
          const hit = this.modules.find((item) => item.filename === this.selectedModule.filename);
          if (hit) {
            this.selectedModule = hit;
          }
        }
      } catch (err) {
        this.modules = [];
        this.totalCount = 0;
        this.boundCount = 0;
        this.unboundCount = 0;
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.modules = false;
      }
    },
    async applyFilter() {
      this.keyword = this.keywordInput.trim();
      await this.refreshModules();
    },

    async saveRoomBinding(item) {
      const roomName = (this.editRoomNames[item.roomid] || "").trim();
      if (!roomName) {
        this.setMessage("群聊名称不能为空", "warn");
        return;
      }

      this.loading.roomBindingId = item.roomid;
      this.clearMessage();
      try {
        if (item.room_name) {
          await apiUpdateRoomBinding(item.roomid, roomName);
          this.setMessage(`群聊映射已更新: ${item.roomid}`, "ok");
        } else {
          await apiCreateRoomBinding(item.roomid, roomName);
          this.setMessage(`群聊映射已创建: ${item.roomid}`, "ok");
        }
        await this.refreshModules();
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.roomBindingId = "";
      }
    },

    async removeRoomBinding(item) {
      if (!item.room_name) {
        this.setMessage("当前模块没有群聊映射可删除", "warn");
        return;
      }

      const ok = window.confirm(`确定删除群聊映射?\nroomid: ${item.roomid}`);
      if (!ok) {
        return;
      }

      this.loading.roomBindingId = item.roomid;
      this.clearMessage();
      try {
        await apiDeleteRoomBinding(item.roomid);
        this.setMessage(`群聊映射已删除: ${item.roomid}`, "ok");
        await this.refreshModules();
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.roomBindingId = "";
      }
    },

    closeViewer() {
      this.showViewer = false;
    },

    async openTextViewer(item) {
      this.selectedModule = item;
      this.showViewer = true;
      this.loading.messages = true;
      this.clearMessage();
      try {
        const data = await getGroupModule(item.filename);
        const rawMessages = data.messages || [];
        this.selectedMessages = this.toStructuredTextMessages(rawMessages);
        this.selectedCount = this.selectedMessages.length;
        this.selectedRawCount = Number(data.count || rawMessages.length || 0);
        this.selectedLatestMsgtime = data.latest_msgtime || item.latest_msgtime || null;
        this.selectedModule = {
          ...item,
          roomid: data.roomid || item.roomid,
          room_name: data.room_name || item.room_name || null,
        };
      } catch (err) {
        this.selectedMessages = [];
        this.selectedCount = 0;
        this.selectedRawCount = 0;
        this.selectedLatestMsgtime = null;
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.messages = false;
      }
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

    quickBindUser(userId) {
      const normalizedId = String(userId || "").trim();
      if (!normalizedId) {
        return;
      }

      this.userForm.user_id = normalizedId;
      const existed = this.userBindings.find((item) => item.user_id === normalizedId);
      this.userForm.nickname = existed ? String(existed.nickname || "") : "";

      const section = document.getElementById("user-binding-section");
      if (section) {
        section.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      this.$nextTick(() => {
        const input = this.$refs.createUserNicknameInput;
        if (input && typeof input.focus === "function") {
          input.focus();
        }
      });
    },

    async refreshUserBindings() {
      this.loading.users = true;
      try {
        const data = await listUserBindings(this.userKeyword);
        this.userBindings = data.items || [];
        this.syncUserEditMap();
      } catch (err) {
        this.userBindings = [];
        this.userEditMap = {};
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.users = false;
      }
    },
    async applyUserFilter() {
      this.userKeyword = this.userKeywordInput.trim();
      await this.refreshUserBindings();
    },

    async createUserNickname() {
      const userId = this.userForm.user_id.trim();
      const nickname = this.userForm.nickname.trim();
      if (!userId || !nickname) {
        this.setMessage("user_id 和 昵称 不能为空", "warn");
        return;
      }

      this.loading.userCreate = true;
      this.clearMessage();
      try {
        await apiCreateUserBinding(userId, nickname);
        this.userForm.user_id = "";
        this.userForm.nickname = "";
        this.setMessage(`用户昵称绑定已创建: ${userId}`, "ok");
        await this.refreshUserBindings();
        await this.refreshModules();
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.userCreate = false;
      }
    },

    async saveUserNickname(item) {
      const nickname = (this.userEditMap[item.user_id] || "").trim();
      if (!nickname) {
        this.setMessage("昵称不能为空", "warn");
        return;
      }

      this.loading.userUpdateId = item.user_id;
      this.clearMessage();
      try {
        await apiUpdateUserBinding(item.user_id, nickname);
        this.setMessage(`用户昵称绑定已更新: ${item.user_id}`, "ok");
        await this.refreshUserBindings();

        if (this.showViewer && this.selectedModule) {
          await this.openTextViewer(this.selectedModule);
        }
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.userUpdateId = "";
      }
    },

    async removeUserBinding(item) {
      const ok = window.confirm(`确定删除用户昵称绑定?\nuser_id: ${item.user_id}`);
      if (!ok) {
        return;
      }

      this.loading.userDeleteId = item.user_id;
      this.clearMessage();
      try {
        await apiDeleteUserBinding(item.user_id);
        this.setMessage(`用户昵称绑定已删除: ${item.user_id}`, "ok");
        await this.refreshUserBindings();

        if (this.showViewer && this.selectedModule) {
          await this.openTextViewer(this.selectedModule);
        }
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.userDeleteId = "";
      }
    },
  },
}).mount("#app");
