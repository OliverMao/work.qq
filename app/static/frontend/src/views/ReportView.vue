<template>
  <div class="report-view">
    <n-card title="学习报告生成">
      <n-form>
        <n-form-item label="选择群聊">
          <n-select
            v-model:value="selectedRoomid"
            :options="chatOptions"
            placeholder="选择群聊"
            filterable
            label-field="label"
            value-field="roomid"
          />
        </n-form-item>
      </n-form>

      <div class="action-bar">
        <n-button type="primary" :loading="loading" @click="doGenerateReport">
          生成报告
        </n-button>
        <n-button @click="loadChats">刷新列表</n-button>
      </div>

      <n-divider />

      <div v-if="report" class="report-content">
        <n-card title="学习报告" :bordered="false" class="report-card">
          <pre>{{ report }}</pre>
        </n-card>
      </div>

      <n-empty v-else-if="!loading && !report" description="点击生成报告" />
    </n-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import {
  NCard,
  NForm,
  NFormItem,
  NSelect,
  NButton,
  NDivider,
  NEmpty,
  useMessage,
} from 'naive-ui';
import { listChats, generateReport as callGenerateReport } from '../services/api-agent.js';

var message = useMessage();

var selectedRoomid = ref(null);
var loading = ref(false);
var report = ref('');
var availableChats = ref([]);
var chatOptions = ref([]);

async function loadChats() {
  try {
    var data = await listChats();
    var items = data.items || [];
    availableChats.value = items;
    chatOptions.value = items.map(function(c) {
      var label = c.room_name || c.roomid;
      if (c.message_count) {
        label = label + ' (' + c.message_count + '条)';
      }
      return { label: label, roomid: c.roomid };
    });
    if (availableChats.value.length === 0) {
      message.warning('没有找到群聊记录');
    }
  } catch (e) {
    message.error('加载群聊失败: ' + e.message);
  }
}

async function doGenerateReport() {
  if (!selectedRoomid.value) {
    message.warning('请选择群聊');
    return;
  }

  try {
    loading.value = true;
    var data = await callGenerateReport(
      selectedRoomid.value,
      null
    );
    if (data.ok === false) {
      message.error('生成失败: ' + (data.error || '未知错误'));
      return;
    }
    report.value = data.report || '';
    if (report.value) {
      message.success('报告生成成功');
    } else {
      message.warning('生成成功但无报告内容');
    }
  } catch (e) {
    console.error('生成失败:', e);
    message.error('生成失败: ' + (e.message || '接口错误'));
  } finally {
    loading.value = false;
  }
}

onMounted(function() {
  loadChats();
});
</script>

<style scoped>
.report-view {
  max-width: 900px;
}
.action-bar {
  display: flex;
  gap: 12px;
}
.report-content {
  margin-top: 16px;
}
.report-card pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  line-height: 1.6;
}
</style>