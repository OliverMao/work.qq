import { createApp } from "https://unpkg.com/vue@3/dist/vue.esm-browser.prod.js";
import { pullArchive } from "/static/frontend/api.js";

createApp({
  data() {
    return {
      loading: {
        pull: false,
      },
      message: {
        text: "",
        type: "ok",
      },
      lastResult: null,
    };
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
    async handlePullArchive() {
      this.loading.pull = true;
      this.clearMessage();
      try {
        const data = await pullArchive();
        this.lastResult = data;
        this.setMessage("拉取成功", "ok");
      } catch (err) {
        this.setMessage(String(err.message || err), "error");
      } finally {
        this.loading.pull = false;
      }
    },
  },
}).mount("#app");
