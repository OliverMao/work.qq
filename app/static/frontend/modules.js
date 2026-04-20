import { createApp } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import {
  listGroupModules,
  getGroupModule,
  createRoomBinding as apiCreateRoomBinding,
  updateRoomBinding as apiUpdateRoomBinding,
  deleteRoomBinding as apiDeleteRoomBinding,
  createUserBinding as apiCreateUserBinding,
  updateUserBinding as apiUpdateUserBinding,
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

      userBindDialog: {
        visible: false,
        userId: "",
        nickname: "",
        saving: false,
      },

      loading: {
        modules: false,
        messages: false,
        roomBindingId: "",
      },
      message: {
        text: "",
        type: "ok",
      },
    };
  },
  mounted() {
    this.refreshModules();
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

    openUserBindDialog(userId, currentDisplay) {
      const normalizedId = String(userId || "").trim();
      if (!normalizedId) {
        return;
      }

      const normalizedDisplay = String(currentDisplay || "").trim();
      this.userBindDialog.userId = normalizedId;
      this.userBindDialog.nickname = normalizedDisplay && normalizedDisplay !== normalizedId
        ? normalizedDisplay
        : "";
      this.userBindDialog.visible = true;
    },

    closeUserBindDialog() {
      if (this.userBindDialog.saving) {
        return;
      }
      this.userBindDialog.visible = false;
    },

    _applyNicknameToSelectedMessages(userId, nickname) {
      const normalizedId = String(userId || "").trim();
      const normalizedNickname = String(nickname || "").trim();
      if (!normalizedId || !normalizedNickname) {
        return;
      }

      this.selectedMessages = this.selectedMessages.map((item) => {
        if (item.from_user_id !== normalizedId) {
          return item;
        }
        return {
          ...item,
          from_display: normalizedNickname,
        };
      });
    },

    async saveUserBindDialog() {
      const userId = String(this.userBindDialog.userId || "").trim();
      const nickname = String(this.userBindDialog.nickname || "").trim();

      if (!userId) {
        this.setMessage("user_id 不能为空", "warn");
        return;
      }
      if (!nickname) {
        this.setMessage("昵称不能为空", "warn");
        return;
      }

      this.userBindDialog.saving = true;
      this.clearMessage();
      try {
        try {
          await apiCreateUserBinding(userId, nickname);
        } catch (err) {
          const errMsg = String(err.message || err);
          if (errMsg.includes("已存在")) {
            await apiUpdateUserBinding(userId, nickname);
          } else {
            throw err;
          }
        }

        this._applyNicknameToSelectedMessages(userId, nickname);
        this.userBindDialog.visible = false;
        this.setMessage(`昵称绑定已保存: ${userId}`, "ok");
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.userBindDialog.saving = false;
      }
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
  },
}).mount("#app");
