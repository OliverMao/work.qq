<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-global-style />
    <n-layout has-sider class="admin-shell">
      <n-layout-sider
        bordered
        collapse-mode="width"
        :collapsed-width="64"
        :width="220"
        :native-scrollbar="false"
        show-trigger="bar"
        class="admin-sider"
        inverted
      >
        <div class="brand-area">
          <div class="brand-mark">QA</div>
          <div class="brand-text">
            <div class="brand-title">会话存档</div>
            <div class="brand-subtitle">管理后台</div>
          </div>
        </div>

        <n-menu
          inverted
          :value="activeMenuKey"
          :options="menuOptions"
          @update:value="handleMenuSelect"
        />
      </n-layout-sider>

      <n-layout>
        <n-layout-header bordered class="admin-header">
          <div class="header-title">{{ currentPageTitle }}</div>
          <div class="header-subtitle">{{ currentPageDescription }}</div>
        </n-layout-header>
        <n-layout-content class="admin-content">
          <div class="content-inner">
            <router-view />
          </div>
        </n-layout-content>
      </n-layout>
    </n-layout>
  </n-config-provider>
</template>

<script setup>
import { computed } from 'vue';
import {
  NConfigProvider,
  NGlobalStyle,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NMenu,
} from 'naive-ui';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

const menuOptions = [
  {
    label: '数据总览',
    key: '/',
  },
  {
    label: '模块管理',
    key: '/modules',
  },
  {
    label: '用户绑定',
    key: '/users',
  },
];

const activeMenuKey = computed(() => route.path);
const currentPageTitle = computed(() => route.meta.title || '会话存档管理');
const currentPageDescription = computed(() => route.meta.description || '');

function handleMenuSelect(key) {
  if (key !== route.path) {
    router.push(key);
  }
}

const themeOverrides = {
  common: {
    primaryColor: '#1677ff',
    primaryColorHover: '#4096ff',
    primaryColorPressed: '#0958d9',
    primaryColorSuppl: '#1677ff',
    borderRadius: '8px',
    fontFamily: '"PingFang SC", "Microsoft YaHei", sans-serif',
  },
  Card: {
    borderRadius: '8px',
  },
  Input: {
    borderRadius: '6px',
  },
  Button: {
    borderRadius: '6px',
  },
  Menu: {
    itemColorInverted: 'transparent',
    itemColorHoverInverted: '#1f2937',
    itemColorActiveInverted: '#1f2937',
    itemColorActiveHoverInverted: '#1f2937',
    itemTextColorInverted: '#cbd5e1',
    itemTextColorHoverInverted: '#ffffff',
    itemTextColorActiveInverted: '#ffffff',
  },
};
</script>