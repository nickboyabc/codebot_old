<template>
  <div class="register-container">
    <div class="register-card">
      <div class="register-header">
        <el-icon class="register-logo"><Monitor /></el-icon>
        <h1>盐城港Agent</h1>
        <p>用户注册</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="register-form"
        @submit.prevent="handleRegister"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            prefix-icon="User"
            size="large"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            prefix-icon="Lock"
            size="large"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="确认密码"
            prefix-icon="Lock"
            size="large"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="register-btn"
            @click="handleRegister"
          >
            注册
          </el-button>
        </el-form-item>
      </el-form>

      <div class="register-footer">
        <span>已有账号？</span>
        <el-link type="primary" @click="router.push('/login')">返回登录</el-link>
      </div>

      <!-- 等待审核提示 -->
      <div v-if="showPendingTip" class="pending-tip">
        <el-icon><Clock /></el-icon>
        <div>
          <p>注册成功，请等待管理员审核</p>
          <p>审核通过后即可登录使用</p>
        </div>
        <el-button type="primary" size="small" @click="router.push('/login')">
          返回登录
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'
import { Monitor, Clock } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()

const formRef = ref(null)
const loading = ref(false)
const showPendingTip = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: ''
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度为 3-32 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const handleRegister = async () => {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    const result = await userStore.register(form.username, form.password)
    if (result?.success) {
      showPendingTip.value = true
    } else {
      ElMessage.error(result?.message || '注册失败，请稍后重试')
    }
  } catch (error) {
    const msg = error?.response?.data?.detail || '注册失败，请稍后重试'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-container {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.register-card {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.register-header {
  text-align: center;
  margin-bottom: 32px;
}

.register-logo {
  font-size: 48px;
  color: #409EFF;
  margin-bottom: 12px;
}

.register-header h1 {
  margin: 0 0 8px;
  font-size: 24px;
  color: #303133;
}

.register-header p {
  margin: 0;
  font-size: 14px;
  color: #909399;
}

.register-form {
  margin-bottom: 24px;
}

.register-btn {
  width: 100%;
}

.register-footer {
  text-align: center;
  font-size: 14px;
  color: #606266;
}

.pending-tip {
  margin-top: 24px;
  padding: 20px;
  background: #f0f9eb;
  border: 1px solid #e1f3d8;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 12px;
  color: #67c23a;
}

.pending-tip p {
  margin: 0;
  font-size: 14px;
}

.pending-tip p:first-child {
  font-weight: bold;
}
</style>
