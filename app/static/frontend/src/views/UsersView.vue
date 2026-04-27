<template>
  <div class="view-section">
    <n-card title="用户绑定管理">
      <n-space vertical :size="12">
        <!-- 标题区 -->
        <div class="section-title-row">
          <div>
            <h3 class="section-title">一键查询并绑定</h3>
            <p class="desc-text">只有企业内部人员、企业客户才可自动获取昵称信息，其余微信用户需手动绑定。</p>
          </div>
          <n-flex wrap :size="8">
            <n-tag round type="info" :bordered="false">候选数: {{ userCandidates.length }}</n-tag>
            <n-tag round type="success" :bordered="false">绑定数: {{ boundCandidateCount }}</n-tag>
          </n-flex>
        </div>

        <n-divider style="margin: 8px 0;" />

        <!-- 筛选与操作区 -->
        <n-flex vertical :size="10">
          <!-- 候选池筛选 -->
          <n-flex align="end" :size="10">
            <div class="search-grow">
              <div class="field-label">候选池筛选</div>
              <n-input
                v-model:value="candidateKeywordInput"
                clearable
                placeholder="按 user_id 过滤候选池"
                @keyup.enter="applyCandidateFilter"
              />
            </div>
            <n-button tertiary :loading="loading.candidates" @click="applyCandidateFilter">
              {{ loading.candidates ? "读取中..." : "读取/筛选候选池" }}
            </n-button>
            <n-button tertiary :loading="loading.candidates" @click="refreshUserCandidates">刷新候选池</n-button>
          </n-flex>

          <!-- 统计标签 -->
          <n-flex wrap :size="8">
            <n-tag round size="small">扫描文件: {{ candidateStats.files_scanned }}</n-tag>
            <n-tag round size="small">扫描消息: {{ candidateStats.messages_scanned }}</n-tag>
            <n-tag round size="small" type="info">可自动查询: {{ autoQueryableCount }}</n-tag>
          </n-flex>

          <n-divider style="margin: 4px 0;" />

          <!-- 一键查询并绑定配置 -->
          <n-flex align="end" :size="12">
            <n-checkbox v-model:checked="autoBindForm.only_unbound">仅处理未绑定用户</n-checkbox>
            <div style="width: 160px;">
              <div class="field-label">最大处理数量</div>
              <n-input-number
                v-model:value="autoBindForm.limit"
                :min="1"
                :max="10000"
                style="width: 100%;"
              />
            </div>
            <n-button type="primary" :loading="loading.autoBind" :disabled="loading.candidates" @click="runAutoBind">
              一键查询并绑定
            </n-button>
          </n-flex>
        </n-flex>
      </n-space>
    </n-card>

    <n-card title="候选用户列表">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width: 28%;">user_id</th>
              <th style="width: 16%;">当前显示名</th>
              <th style="width: 10%;">总次数</th>
              <th style="width: 10%;">from</th>
              <th style="width: 10%;">tolist</th>
              <th style="width: 18%;">绑定</th>
              <th style="width: 16%;">可查询</th>
            </tr>
          </thead>
          <tbody v-if="userCandidates.length > 0">
            <tr v-for="item in userCandidates" :key="item.user_id">
              <td class="mono">{{ item.user_id }}</td>
              <td>{{ item.display_name || item.user_id }}</td>
              <td>{{ item.hit_count || 0 }}</td>
              <td>{{ item.from_count || 0 }}</td>
              <td>{{ item.tolist_count || 0 }}</td>
              <td>
                <n-button size="small" tertiary @click="openBindingDialog(item)">
                  {{ bindingButtonText(item) }}
                </n-button>
              </td>
              <td>
                <n-button
                  size="small"
                  type="success"
                  :loading="loading.queryOneId === item.user_id"
                  :disabled="!item.can_auto_query"
                  @click="queryOneCandidate(item)"
                >
                  {{ item.can_auto_query ? "查询此值" : "不可查询" }}
                </n-button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="userCandidates.length === 0" class="empty-block">
          {{ loading.candidates ? "正在扫描聊天文件..." : "暂无候选 user_id" }}
        </div>
      </div>
    </n-card>

    <n-modal
      :show="bindingDialog.visible"
      preset="card"
      title="修改绑定"
      style="width: min(560px, 95vw);"
      :mask-closable="!loading.bindingSave"
      :closable="!loading.bindingSave"
      @update:show="handleBindingDialogShowChange"
    >
      <n-space vertical :size="12">
        <div>
          <div class="field-label">user_id</div>
          <n-input :value="bindingDialog.user_id" readonly />
        </div>
        <div>
          <div class="field-label">昵称</div>
          <n-input
            v-model:value="bindingDialog.nickname"
            maxlength="128"
            placeholder="请输入昵称"
            @keyup.enter="saveBindingFromDialog"
          />
        </div>
        <n-flex justify="end" :size="10">
          <n-button :disabled="loading.bindingSave" @click="closeBindingDialog">取消</n-button>
          <n-button type="primary" :loading="loading.bindingSave" @click="saveBindingFromDialog">保存</n-button>
        </n-flex>
      </n-space>
    </n-modal>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NFlex,
  NInput,
  NInputNumber,
  NModal,
  NSpace,
  NTag,
  NDivider,
  useMessage,
} from 'naive-ui';
import {
  listArchiveUserCandidates,
  autoBindUserNicknames,
  querySingleUserNickname,
  createUserBinding,
  updateUserBinding,
} from '../services/api';

const message = useMessage();

const candidateKeyword = ref('');
const candidateKeywordInput = ref('');
const candidateStats = ref({
  files_scanned: 0,
  messages_scanned: 0,
});
const autoBindForm = ref({
  only_unbound: true,
  limit: 1000,
});
const bindingDialog = ref({
  visible: false,
  user_id: '',
  nickname: '',
  is_bound: false,
});
const userCandidates = ref([]);
const loading = reactive({
  candidates: false,
  autoBind: false,
  queryOneId: '',
  bindingSave: false,
});

const autoQueryableCount = computed(() => {
  return userCandidates.value.filter((item) => item.can_auto_query).length;
});

const boundCandidateCount = computed(() => {
  return userCandidates.value.filter((item) => item.is_bound).length;
});

onMounted(() => {
  refreshUserCandidates();
});

function formatAction(action) {
  if (action === 'created') {
    return '新增';
  }
  if (action === 'updated') {
    return '更新';
  }
  if (action === 'unchanged') {
    return '不变';
  }
  return action || '-';
}

function bindingButtonText(item) {
  return `修改（${item.is_bound ? '已绑定' : '未绑定'}）`;
}

function openBindingDialog(item) {
  bindingDialog.value = {
    visible: true,
    user_id: item.user_id || '',
    nickname: item.nickname || '',
    is_bound: Boolean(item.is_bound),
  };
}

function closeBindingDialog() {
  if (loading.bindingSave) {
    return;
  }
  bindingDialog.value.visible = false;
}

function handleBindingDialogShowChange(show) {
  if (!show) {
    closeBindingDialog();
  }
}

async function saveBindingFromDialog() {
  if (loading.bindingSave) {
    return;
  }

  const userId = String(bindingDialog.value.user_id || '').trim();
  const nickname = String(bindingDialog.value.nickname || '').trim();
  if (!userId || !nickname) {
    message.warning('user_id 和昵称不能为空');
    return;
  }

  loading.bindingSave = true;
  try {
    if (bindingDialog.value.is_bound) {
      await updateUserBinding(userId, nickname);
    } else {
      await createUserBinding(userId, nickname);
    }
    message.success(`绑定保存成功：${userId} -> ${nickname}`);
    bindingDialog.value.visible = false;
    await refreshUserCandidates();
  } catch (err) {
    message.error(String(err.message || err));
  } finally {
    loading.bindingSave = false;
  }
}

async function queryOneCandidate(item) {
  const userId = String(item.user_id || '').trim();
  if (!userId) {
    message.warning('user_id 为空，无法查询');
    return;
  }

  loading.queryOneId = userId;
  try {
    const data = await querySingleUserNickname(userId);
    const userTypeText = data.user_type === 'external' ? '外部用户' : '内部用户';
    const actionText = formatAction(data.action);
    message.success(`${userId} -> ${data.nickname || '-'}（${userTypeText}，${actionText}）`);
    await refreshUserCandidates();
  } catch (err) {
    message.error(String(err.message || err));
  } finally {
    loading.queryOneId = '';
  }
}

async function refreshUserCandidates() {
  loading.candidates = true;
  try {
    const data = await listArchiveUserCandidates(candidateKeyword.value);
    userCandidates.value = data.items || [];
    candidateStats.value = {
      files_scanned: data.files_scanned || 0,
      messages_scanned: data.messages_scanned || 0,
    };
    message.success(`加载完成：候选数 ${userCandidates.value.length}`);
  } catch (err) {
    userCandidates.value = [];
    candidateStats.value = {
      files_scanned: 0,
      messages_scanned: 0,
    };
    message.error(String(err.message || err));
  } finally {
    loading.candidates = false;
  }
}

async function applyCandidateFilter() {
  candidateKeyword.value = candidateKeywordInput.value.trim();
  await refreshUserCandidates();
}

async function runAutoBind() {
  if (loading.autoBind) {
    return;
  }

  const limit = Math.max(1, Math.min(10000, autoBindForm.value.limit || 1000));
  autoBindForm.value.limit = limit;

  const ok = window.confirm(
    `将自动查询并绑定昵称。\n仅绑定未绑定: ${autoBindForm.value.only_unbound ? '是' : '否'}\n最大处理数量: ${limit}`,
  );
  if (!ok) {
    return;
  }

  loading.autoBind = true;
  try {
    const data = await autoBindUserNicknames({
      keyword: candidateKeyword.value || null,
      only_unbound: autoBindForm.value.only_unbound,
      limit,
    });
    autoBindResult.value = data;

    const summary = `选中 ${data.selected_user_ids || 0}，成功 ${data.success_count || 0}，新增 ${data.created_count || 0}，更新 ${data.updated_count || 0}`;
    
    if (data.failed_count > 0) {
      const failedInfo = data.failed_items?.slice(0, 3).map(item => `${item.user_id}: ${item.error}`).join('；');
      message.warning(`${summary}，失败 ${data.failed_count}（${failedInfo}）`);
    } else {
      message.success(summary);
    }

    await refreshUserCandidates();
  } catch (err) {
    message.error(String(err.message || err));
  } finally {
    loading.autoBind = false;
  }
}
</script>