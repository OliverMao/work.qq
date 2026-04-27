<template>
  <div class="view-section">
    <n-card>
      <n-space vertical :size="14">
        <div class="section-title-row">
          <div>
            <h3 class="section-title">会话同步</h3>
            <p class="desc-text">主动进行会话同步，去重后增量写入本地存档。</p>
          </div>
          <n-button type="primary" :loading="loading.pull" @click="handlePullArchive">
            {{ loading.pull ? "同步中..." : "同步会话" }}
          </n-button>
        </div>

        <n-alert v-if="message.text" :type="messageAlertType" :show-icon="true">
          {{ message.text }}
        </n-alert>
      </n-space>
    </n-card>

    <n-card title="结果说明">
      <!-- <p class="desc-text">保存消息数表示本次新增落盘数量，跳过重复数表示按 msgid 去重后未重复写入的数量。</p> -->
    </n-card>

    <n-card v-if="lastResult" title="本次同步结果">
      <div class="metric-grid">
        <div class="metric-box">
          <div class="metric-label">保存消息数</div>
          <n-statistic :value="lastResult.saved_count || 0" />
        </div>
        <div class="metric-box">
          <div class="metric-label">跳过重复数</div>
          <n-statistic :value="lastResult.skip_duplicate_count || 0" />
        </div>
        <div class="metric-box">
          <div class="metric-label">文件模块数</div>
          <n-statistic :value="(lastResult.files || []).length" />
        </div>
        <div class="metric-box">
          <div class="metric-label">主文件路径</div>
          <div class="mono">{{ lastResult.save_path || "-" }}</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">存档目录</div>
          <div class="mono">{{ lastResult.save_dir || "-" }}</div>
        </div>
      </div>

      <div class="files-scroll" v-if="(lastResult.files || []).length > 0">
        <div class="file-item" v-for="item in lastResult.files" :key="`${item.roomid}-${item.save_path}`">
          <span class="mono">{{ item.roomid }}</span>
          <span>新增 {{ item.count || 0 }} 条 / 总计 {{ item.total_count || 0 }} 条</span>
        </div>
      </div>
    </n-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue';
import { NAlert, NButton, NCard, NSpace, NStatistic } from 'naive-ui';
import { pullArchive } from '../services/api';

const loading = reactive({
  pull: false,
});

const message = ref({
  text: '',
  type: 'ok',
});

const lastResult = ref(null);

const messageAlertType = computed(() => {
  if (message.value.type === 'error') {
    return 'error';
  }
  if (message.value.type === 'warn') {
    return 'warning';
  }
  return 'success';
});

function setMessage(text, type = 'ok') {
  message.value.text = text;
  message.value.type = type;
}

function clearMessage() {
  message.value.text = '';
  message.value.type = 'ok';
}

async function handlePullArchive() {
  loading.pull = true;
  clearMessage();
  try {
    const data = await pullArchive();
    lastResult.value = data;
    setMessage('同步成功', 'ok');
  } catch (err) {
    setMessage(String(err.message || err), 'error');
  } finally {
    loading.pull = false;
  }
}
</script>