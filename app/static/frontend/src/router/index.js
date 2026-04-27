import { createRouter, createWebHistory } from 'vue-router';
import IndexView from '../views/IndexView.vue';
import UsersView from '../views/UsersView.vue';
import ModulesView from '../views/ModulesView.vue';
import AgentView from '../views/AgentView.vue';
import PromptView from '../views/PromptView.vue';

const routes = [
  {
    path: '/',
    name: 'index',
    component: IndexView,
    meta: {
      title: '数据总览',
      description: '执行会话拉取并查看落盘结果与统计信息',
    },
  },
  {
    path: '/users',
    name: 'users',
    component: UsersView,
    meta: {
      title: '用户绑定管理',
      description: '管理 user_id 昵称映射并执行自动查询绑定',
    },
  },
  {
    path: '/modules',
    name: 'modules',
    component: ModulesView,
    meta: {
      title: '群聊管理',
      description: '按会话 JSON 模块维护群聊映射并查看 text 消息',
    },
  },
  {
    path: '/agent',
    name: 'agent',
    component: AgentView,
    meta: {
      title: 'Agent 测试',
      description: '测试 Agent 对话生成和构建向量索引',
    },
  },
  {
    path: '/prompts',
    name: 'prompts',
    component: PromptView,
    meta: {
      title: 'Prompt 管理',
      description: '编辑 Agent 的三个提示词文件',
    },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;