import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import router from '../router'

const request = axios.create({
  // baseURL 为空，调用方使用完整路径如 /api/users
  // Vite proxy 会将 /api 转发到 backend
  baseURL: '',
  timeout: 30000
})

// 标记是否正在处理登出流程，避免循环调用
let isLoggingOut = false

request.interceptors.request.use(config => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})

request.interceptors.response.use(
  response => response,
  error => {
    // 如果正在登出流程中，忽略 401 错误
    if (isLoggingOut) {
      return Promise.reject(error)
    }

    if (error.response?.status === 401) {
      const userStore = useUserStore()

      // 如果还有有效token，说明是token无效/过期
      if (userStore.token) {
        isLoggingOut = true
        userStore.token = ''
        userStore.userInfo = {}
        localStorage.removeItem('token')
        localStorage.removeItem('userInfo')
        router.push('/login')
        // 重置标记，等待下次页面加载
        setTimeout(() => { isLoggingOut = false }, 100)
      }
    }
    return Promise.reject(error)
  }
)

export default request
