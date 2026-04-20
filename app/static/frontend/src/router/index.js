import { createRouter, createWebHistory } from 'vue-router';
import IndexView from '../views/IndexView.vue';
import UsersView from '../views/UsersView.vue';
import ModulesView from '../views/ModulesView.vue';

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
      title: '模块管理',
      description: '按会话 JSON 模块维护群聊映射并查看 text 消息',
    },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;