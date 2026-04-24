<template>
  <div class="prompt-view">
    <n-tabs type="line" v-model:value="activeTab">
      <n-tab-pane name="system_role" tab="system_role.txt">
        <n-card title="系统角色 (system_role.txt)">
          <n-input
            v-model:value="prompts.system_role"
            type="textarea"
            :rows="10"
            placeholder="加载中..."
          />
          <div class="action-bar">
            <n-button type="primary" :loading="saving === 'system_role'" @click="savePromptFile('system_role')">
              保存
            </n-button>
            <n-button @click="loadPrompts">重新加载</n-button>
          </div>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="task_template" tab="task_template.txt">
        <n-card title="任务模板 (task_template.txt)">
          <n-alert type="info" class="mb-3">
            请勿修改变量部分: <n-text code>{stu_message}</n-text> <n-text code>{chat_id}</n-text>
            <n-text code>{history_context}</n-text> <n-text code>{retrieved_context}</n-text>
          </n-alert>
          <n-input
            v-model:value="prompts.task_template"
            type="textarea"
            :rows="12"
            placeholder="加载中..."
          />
          <div class="action-bar">
            <n-button type="primary" :loading="saving === 'task_template'" @click="savePromptFile('task_template')">
              保存
            </n-button>
            <n-button @click="loadPrompts">重新加载</n-button>
          </div>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="constraints" tab="constraints.txt">
        <n-card title="约束规则 (constraints.txt)">
          <n-input
            v-model:value="prompts.constraints"
            type="textarea"
            :rows="10"
            placeholder="加载中..."
          />
          <div class="action-bar">
            <n-button type="primary" :loading="saving === 'constraints'" @click="savePromptFile('constraints')">
              保存
            </n-button>
            <n-button @click="loadPrompts">重新加载</n-button>
          </div>
        </n-card>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import {
  NTabs,
  NTabPane,
  NCard,
  NInput,
  NButton,
  NAlert,
  NText,
  useMessage,
} from 'naive-ui';
import { getPrompt, savePrompt } from '../services/api-agent.js';

const message = useMessage();

const activeTab = ref('system_role');
const saving = ref(null);
const prompts = ref({
  system_role: '',
  task_template: '',
  constraints: '',
});

const fileMap = {
  system_role: 'system_role.txt',
  task_template: 'task_template.txt',
  constraints: 'constraints.txt',
};

async function loadPrompts() {
  for (const [key, filename] of Object.entries(fileMap)) {
    try {
      prompts.value[key] = await getPrompt(filename);
    } catch (e) {
      console.warn(`加载 ${filename} 失败:`, e);
    }
  }
  if (!prompts.value.system_role) {
    message.warning('部分文件加载失败，请检查后端配置');
  }
}

async function savePromptFile(name) {
  const content = prompts.value[name];
  if (content === undefined || content === null) {
    message.warning('内容不能为空');
    return;
  }

  try {
    saving.value = name;
    await savePrompt(fileMap[name], content);
    message.success('保存成功');
  } catch (e) {
    message.error(e.message || '保存失败');
  } finally {
    saving.value = null;
  }
}

onMounted(() => {
  loadPrompts();
});
</script>

<style scoped>
.prompt-view {
  max-width: 900px;
}
.mb-3 {
  margin-bottom: 12px;
}
.action-bar {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}
</style>