<template>
  <div class="prompt-view">
    <n-tabs type="line" v-model:value="activeTab">
      <n-tab-pane name="auto_reply" tab="自动发信">
        <n-card title="自动发信配置">
          <n-form>
            <n-form-item label="使用的模型">
              <n-select v-model:value="autoReply.model" :options="modelOptions" />
            </n-form-item>
            <n-form-item label="发送到群ID">
              <n-input v-model:value="autoReply.target_chatid" placeholder="fangya001" />
            </n-form-item>
          </n-form>
          <div class="action-bar">
            <n-button type="primary" :loading="saving === 'auto_reply'" @click="saveAutoReply">
              保存
            </n-button>
            <n-button @click="loadAutoReply">重新加载</n-button>
          </div>
        </n-card>
      </n-tab-pane>

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

      <n-tab-pane name="report_template" tab="report_template.txt">
        <n-card title="学习报告模板 (report_template.txt)">
          <n-alert type="info" class="mb-3">
            用于生成学习报告的 Prompt 模板
          </n-alert>
          <n-input
            v-model:value="prompts.report_template"
            type="textarea"
            :rows="12"
            placeholder="加载中..."
          />
          <div class="action-bar">
            <n-button type="primary" :loading="saving === 'report_template'" @click="savePromptFile('report_template')">
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
  NSelect,
  NForm,
  NFormItem,
  useMessage,
} from 'naive-ui';
import { getPrompt, savePrompt, getAutoReplyConfig, saveAutoReplyConfig, listAvailableModels } from '../services/api-agent.js';

var message = useMessage();

var activeTab = ref('auto_reply');
var saving = ref(null);
var prompts = ref({
  system_role: '',
  task_template: '',
  constraints: '',
  report_template: '',
});

var autoReply = ref({
  model: 'deepseek/deepseek-v4-flash',
  target_chatid: 'fangya001',
});
var availableModels = ref([]);

var modelOptions = ref([]);

var fileMap = {
  system_role: 'system_role.txt',
  task_template: 'task_template.txt',
  constraints: 'constraints.txt',
  report_template: 'report_template.txt',
};

async function loadModels() {
  try {
    var data = await listAvailableModels();
    availableModels.value = data.models || [];
    modelOptions.value = availableModels.value.map(function(m) {
      return { label: m.name || m.id, value: m.id };
    });
  } catch (e) {
    console.warn('加载模型列表失败:', e);
  }
}

async function loadAutoReply() {
  try {
    var data = await getAutoReplyConfig();
    autoReply.value.model = data.model || 'deepseek/deepseek-v4-flash';
    autoReply.value.target_chatid = data.target_chatid || 'fangya001';
  } catch (e) {
    console.warn('加载自动发信配置失败:', e);
  }
}

async function saveAutoReply() {
  try {
    saving.value = 'auto_reply';
    await saveAutoReplyConfig(autoReply.value.model, autoReply.value.target_chatid);
    message.success('保存成功');
  } catch (e) {
    message.error(e.message || '保存失败');
  } finally {
    saving.value = null;
  }
}

async function loadPrompts() {
  var keys = Object.keys(fileMap);
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    var filename = fileMap[key];
    try {
      prompts.value[key] = await getPrompt(filename);
    } catch (e) {
      console.warn('加载 ' + filename + ' 失败:', e);
    }
  }
  if (!prompts.value.system_role) {
    message.warning('部分文件加载失败，请检查后端配置');
  }
}

async function savePromptFile(name) {
  var content = prompts.value[name];
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

onMounted(function() {
  loadModels();
  loadAutoReply();
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