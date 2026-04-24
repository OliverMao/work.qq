<template>
  <div class="agent-view">
    <n-grid :x-gap="16" :y-gap="16" cols="1 900:2">
      <n-gi>
        <n-card title="对话测试">
          <n-form label-placement="left" label-width="80">
            <n-form-item label="模型">
              <n-input v-model:value="model" placeholder="留空使用默认模型" />
            </n-form-item>
            <n-form-item label="会话ID">
              <n-input-group>
                <n-input v-model:value="chatId" placeholder="输入会话ID" />
                <n-button type="info" @click="loadHistory" :loading="loadingHistory">查询历史</n-button>
              </n-input-group>
            </n-form-item>
            <n-form-item label="学生消息">
              <n-input
                v-model:value="stuMessage"
                type="textarea"
                :rows="4"
                placeholder="输入学生/家长的问题"
              />
            </n-form-item>
          </n-form>
        </n-card>

        <n-card title="历史上下文" class="mt-4">
          <div class="history-add">
            <n-select
              v-model:value="newHistoryRole"
              :options="roleOptions"
              style="width: 100px"
            />
            <n-input
              v-model:value="newHistoryContent"
              placeholder="输入内容"
              style="flex: 1"
            />
            <n-button type="primary" @click="addHistory">添加</n-button>
          </div>
          <div class="history-list" v-if="historyList.length">
            <div v-for="(item, idx) in historyList" :key="idx" class="history-item">
              <n-tag :type="item.role === 'stu' ? 'info' : 'warning'" size="small">
                {{ item.role === 'stu' ? '学生/家长' : '教师' }}
              </n-tag>
              <span class="history-text">{{ item.content }}</span>
              <n-button text type="error" @click="removeHistory(idx)">删除</n-button>
            </div>
          </div>
          <n-empty v-else description="暂无历史记录" size="small" />
        </n-card>

        <div class="action-bar">
          <n-button type="primary" :loading="loading" @click="handleReply" size="large">
            生成回复
          </n-button>
          <n-button @click="clearAll" size="large">清空</n-button>
        </div>
      </n-gi>

      <n-gi>
        <n-card title="向量索引管理">
          <n-space>
            <n-button type="info" :loading="buildingIndex" @click="handleBuildIndex(false)">
              增量构建
            </n-button>
            <n-button type="warning" :loading="buildingIndex" @click="handleBuildIndex(true)">
              全量重建
            </n-button>
          </n-space>
          <div v-if="indexResult" class="index-stats">
            <span>成功: {{ indexResult.ok ? '是' : '否' }}</span>
            <span>添加: {{ indexResult.added_chunk_count }}</span>
            <span>跳过: {{ indexResult.skipped_chunk_count }}</span>
            <span>总计: {{ indexResult.chunk_count }}</span>
          </div>
        </n-card>

        <n-card title="回复结果" v-if="replyResult" class="mt-4">
          <div class="reply-meta">
            <span>模型: {{ replyResult.model || '默认' }}</span>
            <span>检索命中: {{ replyResult.retrieval?.retrieved_count || 0 }}</span>
          </div>
          <n-divider>AI 回复</n-divider>
          <div class="reply-content">{{ replyResult.reply }}</div>
          <div class="context-toggle">
            <n-button text @click="showContext = !showContext">
              {{ showContext ? '收起' : '展开' }}上下文片段 ({{ replyResult.used_context?.length || 0 }})
            </n-button>
          </div>
          <div v-if="showContext && replyResult.used_context?.length" class="context-list">
            <div v-for="(ctx, idx) in replyResult.used_context" :key="idx" class="context-item">
              <div class="context-title">{{ ctx.source_file }}</div>
              <div class="context-meta">
                行 {{ ctx.line_start }}-{{ ctx.line_end }}
              </div>
              <div class="context-content">{{ ctx.content }}</div>
            </div>
          </div>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import {
  NGrid,
  NGi,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NInputGroup,
  NButton,
  NSelect,
  NTag,
  NSpace,
  NDivider,
  useMessage,
} from 'naive-ui';
import { teacherReply, buildAgentIndex, loadHistoryByFilename } from '../services/api-agent.js';

const message = useMessage();

const loading = ref(false);
const loadingHistory = ref(false);
const buildingIndex = ref(false);

const model = ref('');
const chatId = ref('');
const stuMessage = ref('');
const historyList = ref([]);
const newHistoryRole = ref('stu');
const newHistoryContent = ref('');
const replyResult = ref(null);
const indexResult = ref(null);
const showContext = ref(false);

const roleOptions = [
  { label: '学生/家长', value: 'stu' },
  { label: '教师', value: 'tea' },
];

async function loadHistory() {
  if (!chatId.value.trim()) {
    message.warning('请输入会话ID');
    return;
  }
  loadingHistory.value = true;
  try {
    const res = await loadHistoryByFilename(chatId.value.trim() + '.json');
    if (res.messages && res.messages.length) {
      historyList.value = res.messages
        .filter(m => m.from && m.content)
        .map(m => ({
          role: m.from.toLowerCase().includes('wo') || m.from === 'wxwork' ? 'stu' : 'tea',
          content: m.content,
        }));
      message.success(`已加载 ${historyList.value.length} 条记录`);
    } else {
      historyList.value = [];
      message.info('无历史记录');
    }
  } catch (e) {
    message.error('查询失败: ' + (e.message || e));
  } finally {
    loadingHistory.value = false;
  }
}

function addHistory() {
  if (!newHistoryContent.value.trim()) {
    message.warning('请输入内容');
    return;
  }
  historyList.value.push({
    role: newHistoryRole.value,
    content: newHistoryContent.value.trim(),
  });
  newHistoryContent.value = '';
}

function removeHistory(idx) {
  historyList.value.splice(idx, 1);
}

async function handleReply() {
  if (!stuMessage.value.trim()) {
    message.warning('请输入学生消息');
    return;
  }
  loading.value = true;
  try {
    const res = await teacherReply({
      stu_message: stuMessage.value.trim(),
      history: historyList.value.length ? historyList.value : null,
      model: model.value.trim() || null,
    });
    replyResult.value = res;
    message.success('生成成功');
  } catch (e) {
    message.error(e.message || '请求失败');
  } finally {
    loading.value = false;
  }
}

function clearAll() {
  stuMessage.value = '';
  historyList.value = [];
  replyResult.value = null;
  showContext.value = false;
}

async function handleBuildIndex(rebuild = false) {
  buildingIndex.value = true;
  try {
    const res = await buildAgentIndex({ rebuild });
    indexResult.value = res;
    message.success(`构建完成: 添加 ${res.added_chunk_count} 个片段`);
  } catch (e) {
    message.error(e.message || '构建失败');
  } finally {
    buildingIndex.value = false;
  }
}
</script>

<style scoped>
.agent-view {
  max-width: 1200px;
}
.mt-4 {
  margin-top: 16px;
}
.action-bar {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}
.index-stats {
  display: flex;
  gap: 24px;
  margin-top: 16px;
  flex-wrap: wrap;
}
.index-stats span {
  color: #666;
}
.reply-meta {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.reply-meta span {
  color: #666;
}
.reply-content {
  padding: 12px;
  background: #f5f5f5;
  border-radius: 6px;
  white-space: pre-wrap;
  line-height: 1.6;
}
.history-add {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.history-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
}
.history-text {
  flex: 1;
  font-size: 13px;
  color: #333;
  word-break: break-all;
}
.context-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.context-item {
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #eee;
}
.context-title {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}
.context-meta {
  font-size: 11px;
  color: #999;
  margin-bottom: 8px;
}
.context-content {
  font-size: 13px;
  color: #333;
  white-space: pre-wrap;
  line-height: 1.5;
}
.context-toggle {
  margin-top: 12px;
}
</style>