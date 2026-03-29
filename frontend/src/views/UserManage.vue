<template>
  <div class="user-manage-container">
    <div class="page-header">
      <h2>用户管理</h2>
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        创建用户
      </el-button>
    </div>

    <el-table :data="users" v-loading="loading" stripe>
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="role" label="角色" width="100">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
            {{ row.role === 'admin' ? '管理员' : '普通用户' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="180">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <!-- pending 状态：审核通过 / 拒绝 -->
          <template v-if="row.status === 'pending'">
            <el-button size="small" type="success" @click="approveUser(row)">通过</el-button>
            <el-button size="small" type="danger" @click="rejectUser(row)">拒绝</el-button>
          </template>

          <!-- active / suspended 状态：暂停 / 激活 -->
          <template v-else-if="row.status === 'active' || row.status === 'suspended'">
            <el-button
              size="small"
              :type="row.status === 'active' ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '暂停' : '激活' }}
            </el-button>
          </template>

          <!-- 删除按钮（排除自己） -->
          <el-button
            v-if="row.id !== currentUserId"
            size="small"
            type="danger"
            plain
            @click="deleteUser(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建用户对话框 -->
    <el-dialog v-model="createDialogVisible" title="创建用户" width="420px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="70px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-select v-model="createForm.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import request from '../utils/request'
import { useUserStore } from '../stores/user'

const userStore = useUserStore()
const users = ref([])
const loading = ref(false)
const creating = ref(false)
const createDialogVisible = ref(false)
const createFormRef = ref(null)

const currentUserId = computed(() => userStore.userInfo?.id)

const createForm = reactive({
  username: '',
  password: '',
  role: 'user'
})

const createRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度为 3-32 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 个字符', trigger: 'blur' }
  ],
  role: [{ required: true, message: '请选择角色', trigger: 'change' }]
}

const statusLabel = (status) => {
  const map = {
    pending: '待审核',
    active: '正常',
    suspended: '已暂停',
    rejected: '已拒绝'
  }
  return map[status] || status
}

const statusTagType = (status) => {
  const map = {
    pending: 'warning',
    active: 'success',
    suspended: 'danger',
    rejected: 'info'
  }
  return map[status] || ''
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

const loadUsers = async () => {
  loading.value = true
  try {
    const res = await request.get('/api/users')
    if (res.data?.success) {
      users.value = res.data.data
    }
  } catch (error) {
    ElMessage.error('加载用户列表失败')
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  createForm.username = ''
  createForm.password = ''
  createForm.role = 'user'
  createDialogVisible.value = true
}

const handleCreate = async () => {
  if (!createFormRef.value) return
  try {
    await createFormRef.value.validate()
  } catch {
    return
  }

  creating.value = true
  try {
    const res = await request.post('/api/users', {
      username: createForm.username,
      password: createForm.password,
      role: createForm.role
    })
    if (res.data?.success) {
      ElMessage.success('用户创建成功')
      createDialogVisible.value = false
      await loadUsers()
    } else {
      ElMessage.error(res.data?.message || '创建失败')
    }
  } catch (error) {
    const msg = error?.response?.data?.detail || '创建失败'
    ElMessage.error(msg)
  } finally {
    creating.value = false
  }
}

const approveUser = async (row) => {
  try {
    await ElMessageBox.confirm(`审核通过用户 "${row.username}"？`, '审核', {
      confirmButtonText: '通过',
      cancelButtonText: '取消',
      type: 'info'
    })
    await request.put(`/api/users/${row.id}/approve`)
    ElMessage.success('已通过')
    await loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const rejectUser = async (row) => {
  try {
    await ElMessageBox.confirm(`拒绝用户 "${row.username}"？`, '审核', {
      confirmButtonText: '拒绝',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await request.put(`/api/users/${row.id}/reject`)
    ElMessage.success('已拒绝')
    await loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const toggleStatus = async (row) => {
  const action = row.status === 'active' ? '暂停' : '激活'
  try {
    await ElMessageBox.confirm(`${action}用户 "${row.username}"？`, action, {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    const endpoint = row.status === 'active' ? 'suspend' : 'activate'
    await request.put(`/api/users/${row.id}/${endpoint}`)
    ElMessage.success(`已${action}`)
    await loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
    }
  }
}

const deleteUser = async (row) => {
  try {
    await ElMessageBox.confirm(`删除用户 "${row.username}"？此操作不可恢复。`, '删除用户', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'danger'
    })
    await request.delete(`/api/users/${row.id}`)
    ElMessage.success('已删除')
    await loadUsers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.user-manage-container {
  padding: 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}
</style>
