<template>
  <el-menu mode="horizontal" :default-active="$route.path">
    <el-menu-item index="/chat">
      <el-icon><ChatDotRound /></el-icon>
      <span>聊天</span>
    </el-menu-item>

    <template v-if="userStore.isAdmin">
      <el-menu-item index="/users">
        <el-icon><User /></el-icon>
        <span>用户管理</span>
      </el-menu-item>
      <el-menu-item index="/memory">
        <el-icon><Folder /></el-icon>
        <span>记忆</span>
      </el-menu-item>
      <el-menu-item index="/scheduler">
        <el-icon><Clock /></el-icon>
        <span>定时任务</span>
      </el-menu-item>
      <el-menu-item index="/skills">
        <el-icon><Grid /></el-icon>
        <span>技能</span>
      </el-menu-item>
      <el-menu-item index="/mcp">
        <el-icon><Connection /></el-icon>
        <span>MCP</span>
      </el-menu-item>
      <el-menu-item index="/logs">
        <el-icon><Document /></el-icon>
        <span>日志</span>
      </el-menu-item>
      <el-menu-item index="/settings">
        <el-icon><Setting /></el-icon>
        <span>设置</span>
      </el-menu-item>
    </template>

    <div class="user-menu">
      <el-dropdown @command="handleCommand">
        <span class="user-dropdown-link">
          <el-avatar :size="28" icon="User" />
          <span class="username">{{ userStore.userInfo?.username }}</span>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="changePassword">修改密码</el-dropdown-item>
            <el-dropdown-item command="about">关于</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </el-menu>
</template>

<script setup>
import { useUserStore } from '../stores/user'
import { useRouter } from 'vue-router'
import { ChatDotRound, Folder, Clock, Grid, Document, Setting, Connection, User } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const userStore = useUserStore()
const router = useRouter()

const handleCommand = async (command) => {
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定退出登录吗？', '退出登录', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      })
      userStore.logout()
    } catch {
      // cancel
    }
  } else if (command === 'changePassword') {
    showChangePasswordDialog()
  } else if (command === 'about') {
    ElMessageBox.alert(`Codebot 用户管理系统\n版本：1.0.0`, '关于', {
      confirmButtonText: '确定'
    })
  }
}

const showChangePasswordDialog = () => {
  ElMessageBox.prompt('请输入新密码（8位以上，包含字母和数字）', '修改密码', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputType: 'password',
    inputPattern: /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}$/,
    inputErrorMessage: '密码至少8位，需包含字母和数字'
  }).then(({ value }) => {
    userStore.changePassword(value).then(res => {
      if (res.success) {
        ElMessage.success('密码修改成功')
      } else {
        ElMessage.error(res.message || '修改失败')
      }
    })
  }).catch(() => {})
}
</script>

<style scoped>
.user-menu {
  margin-left: auto;
  display: flex;
  align-items: center;
  padding: 0 12px;
}

.user-dropdown-link {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #303133;
}

.user-dropdown-link:hover {
  color: #409EFF;
}

.username {
  font-size: 14px;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
