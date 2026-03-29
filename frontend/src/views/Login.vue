<template>
  <div class="login-page">
    <!-- 左侧企业品牌区域 -->
    <div class="brand-section">
      <div class="brand-content">
        <!-- 企业Logo区域 -->
        <div class="logo-area">
          <div class="company-logo">
            <svg viewBox="0 0 120 120" class="logo-svg">
              <!-- 港口/物流图形 -->
              <circle cx="60" cy="60" r="55" fill="none" stroke="rgba(255,255,255,0.3)" stroke-width="2"/>
              <path d="M30 80 L60 40 L90 80" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M40 80 L60 50 L80 80" fill="none" stroke="rgba(255,255,255,0.6)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="60" cy="35" r="8" fill="#fff"/>
              <line x1="60" y1="43" x2="60" y2="55" stroke="#fff" stroke-width="3"/>
            </svg>
          </div>
          <h1 class="company-name">江蘇盐城港控股集團有限公司</h1>
          <p class="company-slogan">智慧港口 · 數字化管理</p>
        </div>

        <!-- 装饰元素 -->
        <div class="decorative-elements">
          <div class="wave"></div>
          <div class="grid-pattern"></div>
        </div>
      </div>
    </div>

    <!-- 右侧登录表单区域 -->
    <div class="form-section">
      <div class="login-container">
        <div class="login-header">
          <h2>用戶登錄</h2>
          <p>請輸入您的帳戶信息</p>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          class="login-form"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username">
            <div class="input-wrapper">
              <el-icon class="input-icon"><User /></el-icon>
              <el-input
                v-model="form.username"
                placeholder="用戶名 / Username"
                size="large"
                clearable
              />
            </div>
          </el-form-item>

          <el-form-item prop="password">
            <div class="input-wrapper">
              <el-icon class="input-icon"><Lock /></el-icon>
              <el-input
                v-model="form.password"
                type="password"
                placeholder="密碼 / Password"
                size="large"
                show-password
                clearable
              />
            </div>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              class="login-btn"
              @click="handleLogin"
            >
              登 錄
            </el-button>
          </el-form-item>
        </el-form>

        <div class="login-footer">
          <router-link to="/register">沒有帳戶？立即註冊</router-link>
        </div>

        <!-- 测试账户提示（仅调试模式显示） -->
        <div class="test-accounts" v-if="showTestAccounts">
          <div class="divider">
            <span>測試帳戶</span>
          </div>
          <div class="account-cards">
            <div class="account-card admin">
              <div class="card-tag">管理員</div>
              <div class="card-info">
                <span class="label">用戶名：</span>
                <code>admin</code>
              </div>
              <div class="card-info">
                <span class="label">密碼：</span>
                <code>admin123</code>
              </div>
            </div>
            <div class="account-card user">
              <div class="card-tag">普通用戶</div>
              <div class="card-info">
                <span class="label">用戶名：</span>
                <code>user1</code>
              </div>
              <div class="card-info">
                <span class="label">密碼：</span>
                <code>user123</code>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部版权 -->
      <div class="copyright">
        <p>© 2024 江蘇盐城港控股集團有限公司</p>
        <p>版權所有 禁止盜用</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)
const showTestAccounts = ref(true) // 调试模式下显示

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '請輸入用戶名', trigger: 'blur' }],
  password: [{ required: true, message: '請輸入密碼', trigger: 'blur' }]
}

const handleLogin = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    const success = await userStore.login(form.username, form.password)
    if (success) {
      ElMessage.success('登錄成功')
      const redirect = route.query.redirect || '/chat'
      router.push(redirect)
    } else {
      ElMessage.error('用戶名或密碼錯誤')
    }
  } catch (error) {
    const msg = error?.response?.data?.detail || '登錄失敗，請稍後重試'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 整体布局 */
.login-page {
  display: flex;
  min-height: 100vh;
  background: #0a1628;
}

/* 左侧品牌区域 */
.brand-section {
  flex: 1;
  background: linear-gradient(135deg, #1a3a5c 0%, #0d2137 50%, #061525 100%);
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-content {
  position: relative;
  z-index: 2;
  text-align: center;
  padding: 40px;
}

.logo-area {
  margin-bottom: 40px;
}

.company-logo {
  width: 120px;
  height: 120px;
  margin: 0 auto 24px;
  animation: pulse 3s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.05); opacity: 0.9; }
}

.logo-svg {
  width: 100%;
  height: 100%;
}

.company-name {
  font-size: 28px;
  font-weight: 600;
  color: #fff;
  margin: 0 0 12px;
  letter-spacing: 4px;
  text-shadow: 0 2px 10px rgba(0,0,0,0.3);
}

.company-slogan {
  font-size: 16px;
  color: rgba(255,255,255,0.7);
  margin: 0;
  letter-spacing: 2px;
}

/* 装饰元素 */
.decorative-elements {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.wave {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 200px;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 320'%3E%3Cpath fill='%23ffffff' fill-opacity='0.05' d='M0,192L48,197.3C96,203,192,213,288,229.3C384,245,480,267,576,250.7C672,235,768,181,864,181.3C960,181,1056,235,1152,234.7C1248,235,1344,181,1392,154.7L1440,128L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z'%3E%3C/path%3E%3C/svg%3E") no-repeat bottom;
  background-size: cover;
}

.grid-pattern {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 50px 50px;
}

/* 右侧表单区域 */
.form-section {
  width: 480px;
  background: #fff;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 40px;
  position: relative;
}

.login-container {
  width: 100%;
  max-width: 360px;
}

.login-header {
  text-align: center;
  margin-bottom: 40px;
}

.login-header h2 {
  font-size: 28px;
  font-weight: 600;
  color: #1a3a5c;
  margin: 0 0 8px;
}

.login-header p {
  font-size: 14px;
  color: #666;
  margin: 0;
}

/* 输入框样式 */
.input-wrapper {
  position: relative;
  width: 100%;
}

.input-icon {
  position: absolute;
  left: 16px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1;
  color: #999;
  font-size: 18px;
}

:deep(.el-input__wrapper) {
  padding-left: 44px !important;
  height: 48px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  border: 1px solid #e8e8e8;
}

:deep(.el-input__wrapper:hover),
:deep(.el-input__wrapper.is-focus) {
  border-color: #1a3a5c;
  box-shadow: 0 2px 12px rgba(26,58,92,0.15);
}

:deep(.el-input__inner) {
  font-size: 15px;
}

.login-btn {
  width: 100%;
  height: 48px;
  background: linear-gradient(135deg, #1a3a5c 0%, #2d5a87 100%);
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  letter-spacing: 4px;
  color: #fff;
  transition: all 0.3s ease;
}

.login-btn:hover {
  background: linear-gradient(135deg, #2d5a87 0%, #3d7ab8 100%);
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(26,58,92,0.3);
}

.login-btn:active {
  transform: translateY(0);
}

.login-footer {
  text-align: center;
  margin-top: 24px;
  font-size: 14px;
}

.login-footer a {
  color: #1a3a5c;
  text-decoration: none;
  font-weight: 500;
}

.login-footer a:hover {
  text-decoration: underline;
}

/* 测试账户卡片 */
.test-accounts {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px dashed #e0e0e0;
}

.divider {
  text-align: center;
  margin-bottom: 16px;
  position: relative;
}

.divider span {
  background: #fff;
  padding: 0 16px;
  color: #999;
  font-size: 12px;
  position: relative;
  z-index: 1;
}

.account-cards {
  display: flex;
  gap: 12px;
}

.account-card {
  flex: 1;
  padding: 12px;
  border-radius: 8px;
  background: #f8f9fa;
  border: 1px solid #eee;
}

.account-card.admin {
  border-left: 3px solid #e6a23c;
}

.account-card.user {
  border-left: 3px solid #67c23a;
}

.card-tag {
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 8px;
  letter-spacing: 1px;
}

.account-card.admin .card-tag {
  color: #e6a23c;
}

.account-card.user .card-tag {
  color: #67c23a;
}

.card-info {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-info .label {
  color: #999;
}

.card-info code {
  font-family: Consolas, Monaco, monospace;
  background: #fff;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
}

/* 版权信息 */
.copyright {
  position: absolute;
  bottom: 20px;
  text-align: center;
  font-size: 11px;
  color: #999;
}

.copyright p {
  margin: 0;
  line-height: 1.6;
}

/* 响应式 */
@media (max-width: 900px) {
  .login-page {
    flex-direction: column;
  }

  .brand-section {
    padding: 40px 20px;
    min-height: auto;
  }

  .company-name {
    font-size: 22px;
    letter-spacing: 2px;
  }

  .form-section {
    width: 100%;
    padding: 30px 20px;
  }
}
</style>
