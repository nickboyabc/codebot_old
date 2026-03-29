import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'

import MemoryView from '@/views/Memory.vue'
import ActiveMemoriesView from '@/components/ActiveMemories.vue'
import MemorySearchView from '@/components/MemorySearch.vue'
import ArchivedMemoriesView from '@/components/ArchivedMemories.vue'
import BackupRestoreView from '@/components/BackupRestore.vue'
import MemoryConfigView from '@/components/MemoryConfig.vue'

const routes = [
  {
    path: '/',
    redirect: '/chat'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/Chat.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/memory',
    name: 'Memory',
    component: MemoryView,
    children: [
      {
        path: '',
        redirect: '/memory/active'
      },
      {
        path: 'active',
        name: 'ActiveMemories',
        component: ActiveMemoriesView
      },
      {
        path: 'search',
        name: 'MemorySearch',
        component: MemorySearchView
      },
      {
        path: 'archived',
        name: 'ArchivedMemories',
        component: ArchivedMemoriesView
      },
      {
        path: 'backup',
        name: 'MemoryBackup',
        component: BackupRestoreView
      },
      {
        path: 'config',
        name: 'MemoryConfig',
        component: MemoryConfigView
      }
    ]
  },
  {
    path: '/users',
    name: 'UserManage',
    component: () => import('@/views/UserManage.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/scheduler',
    name: 'Scheduler',
    component: () => import('@/views/Scheduler.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/skills',
    name: 'Skills',
    component: () => import('@/views/Skills.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/mcp',
    name: 'MCP',
    component: () => import('@/views/MCP.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('@/views/Logs.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()

  if (to.meta.requiresAuth === false) {
    if (userStore.isLoggedIn) return next('/chat')
    return next()
  }

  if (!userStore.isLoggedIn) {
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }

  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    ElMessage.warning('您没有权限访问该页面')
    return next('/chat')
  }

  next()
})

router.onError((error) => {
  const message = String(error?.message || '')
  const isChunkLoadError =
    message.includes('Failed to fetch dynamically imported module') ||
    message.includes('Importing a module script failed') ||
    message.includes('Loading chunk') ||
    message.includes('ChunkLoadError')
  if (isChunkLoadError) {
    window.location.reload()
  }
})

export default router
