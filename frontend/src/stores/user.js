import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import request from '../utils/request'
import router from '../router'

/**
 * 用户状态管理
 *
 * token 和 userInfo 都存储在 localStorage 中，页面刷新后自动恢复会话。
 *
 * 安全说明：
 * - 如果需要更高安全性，应由后端在登录时设置 httpOnly SameSite=Strict Cookie 存 refresh_token
 * - 前端登录后用 refresh_token 自动续期 access_token 存内存
 * - 页面刷新时调用 /api/auth/refresh 获取新 token
 */
export const useUserStore = defineStore('user', () => {
  // token 存 localStorage（页面刷新后恢复会话）
  const token = ref(localStorage.getItem('token') || '')
  // userInfo 存 localStorage（username/role/status，仅用于 UI 渲染）
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || '{}'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userInfo.value?.role === 'admin')
  const isActive = computed(() => userInfo.value?.status === 'active')

  async function login(username, password) {
    const res = await request.post('/api/auth/login', { username, password })
    if (res.data?.success) {
      setLogin(res.data.data)
      return true
    }
    return false
  }

  async function register(username, password) {
    const res = await request.post('/api/auth/register', { username, password })
    return res.data
  }

  function setLogin({ access_token, user }) {
    token.value = access_token
    userInfo.value = user
    // 持久化 token 和 userInfo 到 localStorage
    localStorage.setItem('token', access_token)
    localStorage.setItem('userInfo', JSON.stringify(user))
  }

  function logout() {
    // 先清理本地状态
    token.value = ''
    userInfo.value = {}
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')

    // 调用API（不等待）
    request.post('/api/auth/logout').catch(() => {})

    // 跳转
    router.push('/login')
  }

  async function fetchCurrentUser() {
    if (!token.value) return
    try {
      const res = await request.get('/api/auth/me')
      if (res.data?.success) {
        userInfo.value = res.data.data
        localStorage.setItem('userInfo', JSON.stringify(res.data.data))
      }
    } catch {
      // token 失效，清理状态
      logout()
    }
  }

  async function changePassword(oldPassword, newPassword) {
    try {
      const res = await request.post('/api/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword
      })
      return res.data || { success: true }
    } catch (e) {
      return { success: false, message: e.response?.data?.detail || '修改失败' }
    }
  }

  return { token, userInfo, isLoggedIn, isAdmin, isActive, login, register, setLogin, logout, fetchCurrentUser, changePassword }
})
