<template>
  <div class="app-container">
    <el-alert v-if="stat.length" type="info" :closable="false" show-icon class="stat-bar">
      <template #title>
        <el-tag v-for="s in stat" :key="s.name" size="small"
                :type="s.name === 'sent' ? 'success' : (s.name === 'failed' ? 'danger' : 'info')"
                style="margin-right: 8px">{{ label(s.name) }} {{ s.cnt }}</el-tag>
        <span class="dim">共 {{ total }} 条</span>
      </template>
    </el-alert>

    <el-form :model="query" :inline="true" class="qform">
      <el-form-item label="讲座">
        <el-input v-model="query.lectureTitle" placeholder="讲座名关键字" clearable
                  style="width: 180px" @keyup.enter="getList" />
      </el-form-item>
      <el-form-item label="接收人">
        <el-input v-model="query.subscriberName" placeholder="姓名" clearable
                  style="width: 120px" @keyup.enter="getList" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.sendStatus" placeholder="全部" clearable style="width: 110px" @change="getList">
          <el-option label="已发送" value="sent" />
          <el-option label="失败" value="failed" />
          <el-option label="跳过" value="skipped" />
          <el-option label="待发" value="pending" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="getList">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="list" size="small">
      <el-table-column label="讲座" prop="lectureTitle" min-width="200" show-overflow-tooltip />
      <el-table-column label="接收人" prop="subscriberName" width="110">
        <template #default="{ row }">{{ row.subscriberName || '（基线登记）' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small"
                  :type="row.sendStatus === 'sent' ? 'success' : (row.sendStatus === 'failed' ? 'danger' : 'info')">
            {{ label(row.sendStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="重试" prop="attempt" width="70" align="center" />
      <el-table-column label="发送时间" width="150">
        <template #default="{ row }">{{ row.sentTime || '—' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="150" prop="createTime" />
      <el-table-column label="备注" prop="lastError" min-width="160" show-overflow-tooltip />
    </el-table>

    <pagination v-show="total > 0" :total="total" v-model:page="query.pageNum"
                v-model:limit="query.pageSize" @pagination="getList" />
  </div>
</template>

<script setup name="LectureDelivery">
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'

const loading = ref(false)
const list = ref([])
const total = ref(0)
const stat = ref([])

const query = reactive({
  pageNum: 1,
  pageSize: 20,
  lectureTitle: '',
  subscriberName: '',
  sendStatus: ''
})

function label(s) {
  return ({ sent: '已发送', failed: '失败', skipped: '跳过', pending: '待发' })[s] || s || '-'
}

function getList() {
  loading.value = true
  request({ url: '/system/lecture/delivery/list', method: 'get', params: query })
    .then(res => {
      list.value = res.rows || []
      total.value = res.total || 0
    })
    .catch(() => {})
    .finally(() => { loading.value = false })
}

function getStat() {
  request({ url: '/system/lecture/delivery/stat', method: 'get' })
    .then(res => {
      const d = (res && res.data) ? res.data : (res || [])
      stat.value = Array.isArray(d) ? d : []
    })
    .catch(() => {})
}

function resetQuery() {
  query.lectureTitle = ''
  query.subscriberName = ''
  query.sendStatus = ''
  query.pageNum = 1
  getList()
}

onMounted(() => { getList(); getStat() })
</script>

<style scoped>
.stat-bar { margin-bottom: 14px; }
.qform { margin-bottom: 4px; }
.dim { color: #909399; font-size: 12.5px; }
</style>
