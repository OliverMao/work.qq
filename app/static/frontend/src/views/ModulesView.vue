<template>
  <div class="view-section">
    <n-card>
      <n-space vertical :size="12">
        <div class="section-title-row">
          <div>
            <h3 class="section-title">模块筛选</h3>
            <p class="desc-text">按文件名或 roomid 管理 JSON 模块，维护群聊名称绑定并查看 text 消息。</p>
          </div>
          <n-tag :bordered="false" type="info">模块总数: {{ totalCount }}</n-tag>
        </div>

        <n-flex wrap align="end" :size="10">
          <div class="search-grow">
            <div class="field-label">关键字</div>
            <n-input
              v-model:value="keywordInput"
              clearable
              placeholder="按文件名或 roomid 过滤"
              @keyup.enter="applyFilter"
            />
          </div>
          <n-button type="primary" :loading="loading.modules" @click="applyFilter">查询</n-button>
          <n-button tertiary :loading="loading.modules" @click="refreshModules">刷新</n-button>
        </n-flex>

        <n-flex wrap :size="8">
          <n-tag round>当前筛选: {{ keyword || "全部" }}</n-tag>
          <n-tag round type="success">已绑定 room: {{ boundCount }}</n-tag>
          <n-tag round type="warning">未绑定 room: {{ unboundCount }}</n-tag>
        </n-flex>

        <n-alert v-if="message.text" :type="messageAlertType" :show-icon="true">
          {{ message.text }}
        </n-alert>
      </n-space>
    </n-card>

    <n-card title="模块列表">
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width: 17%;">roomid</th>
              <th style="width: 30%;">群聊名称绑定</th>
              <th style="width: 10%;">消息数</th>
              <th style="width: 12%;">最后消息时间</th>
              <th style="width: 15%;">操作</th>
            </tr>
          </thead>
          <tbody v-if="modules.length > 0">
            <tr
              v-for="item in modules"
              :key="item.filename"
              :class="{ 'selected-row': selectedModule && selectedModule.filename === item.filename }"
            >
              <td class="mono">
                <div>{{ item.roomid }}</div>
                 <n-tag v-if="item.parse_error" size="small" type="error" :bordered="false">解析异常</n-tag>


              </td>
              <td>
                
                <n-flex class="row-actions" wrap :size="8">
                    <n-tag size="small" :type="item.room_name ? 'success' : 'warning'" :bordered="false">
                  {{ item.room_name ? '已绑定' : '未绑定' }}
                </n-tag>
                  <n-input
                    :value="editRoomNames[item.roomid] || ''"
                    style="max-width: 200px;"
                    maxlength="128"
                    placeholder="输入群聊昵称"
                    @update:value="(value) => onEditRoomName(item.roomid, value)"
                  />
                  <n-button
                    size="small"
                    type="success"
                    :loading="loading.roomBindingId === item.roomid"
                    @click="saveRoomBinding(item)"
                  >
                    保存
                  </n-button>
                  <n-button
                    size="small"
                    type="error"
                    :disabled="loading.roomBindingId === item.roomid || !item.room_name"
                    @click="removeRoomBinding(item)"
                  >
                    删除
                  </n-button>
                </n-flex>
              </td>
              <td>{{ item.message_count || 0 }}</td>
              <td>{{ formatUnixTime(item.latest_msgtime) }}</td>
              <td>
                <n-button
                  tertiary
                  size="small"
                  :loading="loading.messages && selectedModule && selectedModule.filename === item.filename"
                  @click="openTextViewer(item)"
                >
                  查看 text
                </n-button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="modules.length === 0" class="empty-block">
          {{ loading.modules ? "正在加载模块..." : "暂无模块数据" }}
        </div>
      </div>
    </n-card>

    <n-modal
      v-model:show="showViewer"
      preset="card"
      title="text 消息结构化查看"
      style="width: min(1220px, 96vw);"
      :mask-closable="true"
      :closable="true"
    >
      <n-space vertical :size="12" class="viewer-layout">
        <div class="viewer-summary-grid">
          <div class="viewer-meta-card">
            <div class="viewer-meta-label">文件</div>
            <div class="viewer-meta-value mono">{{ selectedModule ? selectedModule.filename : '-' }}</div>
          </div>
          <div class="viewer-meta-card">
            <div class="viewer-meta-label">roomid</div>
            <div class="viewer-meta-value mono">{{ selectedModule ? selectedModule.roomid : '-' }}</div>
          </div>
          <div class="viewer-meta-card">
            <div class="viewer-meta-label">绑定群名</div>
            <n-tag size="small" :type="selectedModule && selectedModule.room_name ? 'success' : 'warning'" :bordered="false">
              {{ selectedModule ? (selectedModule.room_name || '未绑定') : '未绑定' }}
            </n-tag>
          </div>
          <div class="viewer-meta-card">
            <div class="viewer-meta-label">最近消息时间</div>
            <div class="viewer-meta-value">{{ formatUnixTime(selectedLatestMsgtime) }}</div>
          </div>
        </div>

        <div class="viewer-metrics-grid">
          <div class="viewer-metric-card">
            <div class="viewer-metric-label">text消息数</div>
            <div class="viewer-metric-value">{{ selectedCount }}</div>
          </div>
          <div class="viewer-metric-card">
            <div class="viewer-metric-label">原始消息数</div>
            <div class="viewer-metric-value">{{ selectedRawCount }}</div>
          </div>
        </div>

        <div class="table-wrap viewer-table-wrap" v-if="selectedMessages.length > 0">
          <table>
            <thead>
              <tr>
                <th style="width: 56px;">#</th>
                <th style="width: 200px;">msgid</th>
                <th style="width: 240px;">from</th>
                <th style="width: 100px;">action</th>
                <th style="width: 200px;">roomid</th>
                <th style="width: 100px;">msgtype</th>
                <th style="width: 380px;">text:content</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(msg, idx) in selectedMessages" :key="msg.msgid || idx">
                <td>{{ idx + 1 }}</td>
                <td class="mono">{{ msg.msgid }}</td>
                <td>
                  <div>{{ msg.from_display }}</div>
                  <div class="muted-text" v-if="msg.from_display !== msg.from_user_id">{{ msg.from_user_id }}</div>
                  <n-button
                    tertiary
                    size="tiny"
                    class="viewer-user-bind-btn"
                    @click="openUserBindDialog(msg.from_user_id, msg.from_display)"
                  >
                    {{ msg.from_display === msg.from_user_id ? "绑定昵称" : "修改昵称" }}
                  </n-button>
                </td>
                <td>{{ msg.action }}</td>
                <td class="mono">{{ msg.roomid }}</td>
                <td>{{ msg.msgtype }}</td>
                <td class="content-cell">{{ msg.text_content }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="empty-block">
          {{ loading.messages ? "正在加载群聊内容..." : "当前模块暂无 text 类型消息" }}
        </div>
      </n-space>
    </n-modal>

    <n-modal
      :show="userBindDialog.visible"
      preset="card"
      title="绑定用户昵称"
      style="width: min(560px, 95vw);"
      :mask-closable="!userBindDialog.saving"
      :closable="!userBindDialog.saving"
      @update:show="handleUserBindDialogShowChange"
    >
      <n-space vertical :size="12">
        <p class="desc-text">绑定后，消息中的 from 将优先显示昵称。</p>
        <div>
          <div class="field-label">user_id</div>
          <n-input :value="userBindDialog.userId" readonly />
        </div>

        <div>
          <div class="field-label">昵称</div>
          <n-input
            v-model:value="userBindDialog.nickname"
            maxlength="128"
            placeholder="请输入昵称"
            @keyup.enter="saveUserBindDialog"
          />
        </div>

        <n-flex justify="end" :size="10">
          <n-button :disabled="userBindDialog.saving" @click="closeUserBindDialog">取消</n-button>
          <n-button type="primary" :loading="userBindDialog.saving" @click="saveUserBindDialog">保存昵称</n-button>
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
  NFlex,
  NInput,
  NModal,
  NSpace,
  NTag,
} from 'naive-ui';
import {
  listGroupModules,
  getGroupModule,
  createRoomBinding as apiCreateRoomBinding,
  updateRoomBinding as apiUpdateRoomBinding,
  deleteRoomBinding as apiDeleteRoomBinding,
  createUserBinding as apiCreateUserBinding,
  updateUserBinding as apiUpdateUserBinding,
} from '../services/api';

const modules = ref([]);
const totalCount = ref(0);
const boundCount = ref(0);
const unboundCount = ref(0);
const keyword = ref('');
const keywordInput = ref('');
const editRoomNames = ref({});

const selectedModule = ref(null);
const showViewer = ref(false);
const selectedMessages = ref([]);
const selectedCount = ref(0);
const selectedRawCount = ref(0);
const selectedLatestMsgtime = ref(null);

const userBindDialog = ref({
  visible: false,
  userId: '',
  nickname: '',
  saving: false,
});

const loading = reactive({
  modules: false,
  messages: false,
  roomBindingId: '',
});
const message = ref({
  text: '',
  type: 'ok',
});

const messageAlertType = computed(() => {
  if (message.value.type === 'error') {
    return 'error';
  }
  if (message.value.type === 'warn') {
    return 'warning';
  }
  return 'success';
});

onMounted(() => {
  refreshModules();
});

function setMessage(text, type = 'ok') {
  message.value.text = text;
  message.value.type = type;
}

function clearMessage() {
  message.value.text = '';
  message.value.type = 'ok';
}

function formatUnixTime(value) {
  if (!value || Number(value) <= 0) {
    return '-';
  }
  const ts = Number(value);
  const date = new Date(ts >= 1000000000000 ? ts : ts * 1000);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString('zh-CN', { hour12: false });
}

function normalizeTextContent(messageItem) {
  const textPayload = messageItem && messageItem.text;
  const content = textPayload && textPayload.content;
  if (content === null || content === undefined) {
    return '';
  }
  return String(content);
}

function toStructuredTextMessages(messages) {
  if (!Array.isArray(messages)) {
    return [];
  }

  return messages
    .filter((msg) => String((msg && msg.msgtype) || '').toLowerCase() === 'text')
    .map((msg) => {
      const userId = String(msg.from || '');
      const display = String(msg.from_display || msg.from_nickname || msg.from || '');
      return {
        msgid: String(msg.msgid || ''),
        from_user_id: userId,
        from_display: display || userId,
        action: String(msg.action || ''),
        roomid: String(msg.roomid || ''),
        msgtype: String(msg.msgtype || ''),
        text_content: normalizeTextContent(msg),
      };
    });
}

function buildRoomBindingCounts() {
  const bound = modules.value.filter((item) => !!item.room_name).length;
  boundCount.value = bound;
  unboundCount.value = modules.value.length - bound;
}

function syncRoomEditMap() {
  const map = {};
  modules.value.forEach((item) => {
    map[item.roomid] = item.room_name || '';
  });
  editRoomNames.value = map;
}

function onEditRoomName(roomid, value) {
  editRoomNames.value = {
    ...editRoomNames.value,
    [roomid]: value,
  };
}

async function refreshModules() {
  loading.modules = true;
  try {
    const data = await listGroupModules(keyword.value);
    modules.value = data.items || [];
    totalCount.value = Number(data.count || 0);
    buildRoomBindingCounts();
    syncRoomEditMap();

    if (selectedModule.value) {
      const hit = modules.value.find((item) => item.filename === selectedModule.value.filename);
      if (hit) {
        selectedModule.value = hit;
      }
    }
  } catch (err) {
    modules.value = [];
    totalCount.value = 0;
    boundCount.value = 0;
    unboundCount.value = 0;
    setMessage(String(err.message || err), 'error');
  } finally {
    loading.modules = false;
  }
}

async function applyFilter() {
  keyword.value = keywordInput.value.trim();
  await refreshModules();
}

async function saveRoomBinding(item) {
  const roomName = (editRoomNames.value[item.roomid] || '').trim();
  if (!roomName) {
    setMessage('群聊名称不能为空', 'warn');
    return;
  }

  loading.roomBindingId = item.roomid;
  clearMessage();
  try {
    if (item.room_name) {
      await apiUpdateRoomBinding(item.roomid, roomName);
      setMessage(`群聊映射已更新: ${item.roomid}`, 'ok');
    } else {
      await apiCreateRoomBinding(item.roomid, roomName);
      setMessage(`群聊映射已创建: ${item.roomid}`, 'ok');
    }
    await refreshModules();
  } catch (err) {
    setMessage(String(err.message || err), 'error');
  } finally {
    loading.roomBindingId = '';
  }
}

async function removeRoomBinding(item) {
  if (!item.room_name) {
    setMessage('当前模块没有群聊映射可删除', 'warn');
    return;
  }

  const ok = window.confirm(`确定删除群聊映射?\nroomid: ${item.roomid}`);
  if (!ok) {
    return;
  }

  loading.roomBindingId = item.roomid;
  clearMessage();
  try {
    await apiDeleteRoomBinding(item.roomid);
    setMessage(`群聊映射已删除: ${item.roomid}`, 'ok');
    await refreshModules();
  } catch (err) {
    setMessage(String(err.message || err), 'error');
  } finally {
    loading.roomBindingId = '';
  }
}

function openUserBindDialog(userId, currentDisplay) {
  const normalizedId = String(userId || '').trim();
  if (!normalizedId) {
    return;
  }

  const normalizedDisplay = String(currentDisplay || '').trim();
  userBindDialog.value.userId = normalizedId;
  userBindDialog.value.nickname = normalizedDisplay && normalizedDisplay !== normalizedId
    ? normalizedDisplay
    : '';
  userBindDialog.value.visible = true;
}

function closeUserBindDialog() {
  if (userBindDialog.value.saving) {
    return;
  }
  userBindDialog.value.visible = false;
}

function handleUserBindDialogShowChange(show) {
  if (!show) {
    closeUserBindDialog();
  }
}

function applyNicknameToSelectedMessages(userId, nickname) {
  const normalizedId = String(userId || '').trim();
  const normalizedNickname = String(nickname || '').trim();
  if (!normalizedId || !normalizedNickname) {
    return;
  }

  selectedMessages.value = selectedMessages.value.map((item) => {
    if (item.from_user_id !== normalizedId) {
      return item;
    }
    return {
      ...item,
      from_display: normalizedNickname,
    };
  });
}

async function saveUserBindDialog() {
  const userId = String(userBindDialog.value.userId || '').trim();
  const nickname = String(userBindDialog.value.nickname || '').trim();

  if (!userId) {
    setMessage('user_id 不能为空', 'warn');
    return;
  }
  if (!nickname) {
    setMessage('昵称不能为空', 'warn');
    return;
  }

  userBindDialog.value.saving = true;
  clearMessage();
  try {
    try {
      await apiCreateUserBinding(userId, nickname);
    } catch (err) {
      const errMsg = String(err.message || err);
      if (errMsg.includes('已存在')) {
        await apiUpdateUserBinding(userId, nickname);
      } else {
        throw err;
      }
    }

    applyNicknameToSelectedMessages(userId, nickname);
    userBindDialog.value.visible = false;
    setMessage(`昵称绑定已保存: ${userId}`, 'ok');
  } catch (err) {
    setMessage(String(err.message || err), 'error');
  } finally {
    userBindDialog.value.saving = false;
  }
}

async function openTextViewer(item) {
  selectedModule.value = item;
  showViewer.value = true;
  loading.messages = true;
  clearMessage();
  try {
    const data = await getGroupModule(item.filename);
    const rawMessages = data.messages || [];
    selectedMessages.value = toStructuredTextMessages(rawMessages);
    selectedCount.value = selectedMessages.value.length;
    selectedRawCount.value = Number(data.count || rawMessages.length || 0);
    selectedLatestMsgtime.value = data.latest_msgtime || item.latest_msgtime || null;
    selectedModule.value = {
      ...item,
      roomid: data.roomid || item.roomid,
      room_name: data.room_name || item.room_name || null,
    };
  } catch (err) {
    selectedMessages.value = [];
    selectedCount.value = 0;
    selectedRawCount.value = 0;
    selectedLatestMsgtime.value = null;
    setMessage(String(err.message || err), 'error');
  } finally {
    loading.messages = false;
  }
}
</script>