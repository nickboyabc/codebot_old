<template>
  <div class="memory-search">
    <div class="search-actions">
      <el-input
        v-model="query"
        placeholder="输入关键词搜索记忆"
        clearable
        style="max-width: 420px"
        @keyup.enter="searchMemories"
      />
      <el-select v-model="category" clearable placeholder="全部类别" style="width: 140px; margin-left: 8px">
        <el-option v-for="cat in categories" :key="cat.value" :label="cat.label" :value="cat.value" />
      </el-select>
      <el-input-number v-model="topK" :min="1" :max="50" style="margin-left: 8px; width: 120px" />
      <el-checkbox v-model="includeArchived" style="margin-left: 10px">
        包含归档
      </el-checkbox>
      <el-button type="primary" :loading="searching" style="margin-left: 8px" @click="searchMemories">
        搜索
      </el-button>
    </div>

    <el-alert
      class="search-hint"
      type="info"
      :closable="false"
      show-icon
      :title="`当前“包含归档”默认值来自记忆配置：${includeArchivedDefault ? '开启' : '关闭'}`"
    />

    <el-empty v-if="!searching && results.length === 0" description="暂无搜索结果" />

    <el-table v-else :data="results" style="width: 100%">
      <el-table-column prop="category" label="类别" width="120" />
      <el-table-column prop="content" label="内容" min-width="320" />
      <el-table-column label="相似度" width="120">
        <template #default="{ row }">
          {{ formatScore(row.distance) }}
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../utils/request'

const query = ref('')
const category = ref('')
const topK = ref(10)
const includeArchived = ref(false)
const includeArchivedDefault = ref(false)
const searching = ref(false)
const results = ref([])

const categories = [
  { value: 'habit', label: '习惯' },
  { value: 'preference', label: '偏好' },
  { value: 'profile', label: '个人信息' },
  { value: 'note', label: '笔记' },
  { value: 'contact', label: '联系人' },
  { value: 'address', label: '地址' },
]

const loadConfig = async () => {
  try {
    const response = await request.get('/api/memory/config')
    const enabled = Boolean(response.data?.data?.show_archived_in_search)
    includeArchived.value = enabled
    includeArchivedDefault.value = enabled
  } catch (error) {
    includeArchived.value = false
    includeArchivedDefault.value = false
  }
}

const searchMemories = async () => {
  if (!query.value.trim()) {
    ElMessage.warning('请输入关键词')
    return
  }
  searching.value = true
  try {
    const params = {
      query: query.value.trim(),
      top_k: topK.value,
      include_archived: includeArchived.value
    }
    if (category.value) params.category = category.value
    const response = await request.get('/api/memory/memories/search', { params })
    results.value = response.data.data || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '搜索失败')
  } finally {
    searching.value = false
  }
}

const formatScore = (distance) => {
  const d = Number(distance)
  if (!Number.isFinite(d)) return '-'
  const score = Math.max(0, Math.min(1, 1 - d))
  return `${(score * 100).toFixed(1)}%`
}

onMounted(loadConfig)
</script>

<style scoped>
.memory-search {
  padding: 4px 0;
}
.search-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
  margin-bottom: 12px;
}
.search-hint {
  margin-bottom: 12px;
}
</style>
