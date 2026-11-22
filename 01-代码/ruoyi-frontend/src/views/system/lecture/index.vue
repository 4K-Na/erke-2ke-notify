<template>
  <div class="app-container lecture-page">
    <!-- 采集器状态 -->
    <el-alert
      :type="collectorOk ? 'success' : 'warning'"
      :closable="false" show-icon class="status-bar"
    >
      <template #title>
        <span v-if="collectorOk">
          采集正常 · 最近成功 {{ state.last_ok }} · 库里 {{ stat.total || 0 }} 场（开放 {{ stat.openCnt || 0 }}，可报名 {{ stat.canJoinCnt || 0 }}）
        </span>
        <span v-else>
          采集异常：{{ state.last_error || '未知' }} —— 点下面「更新登录态」贴新的 Cookie
        </span>
      </template>
    </el-alert>

    <el-form :model="query" :inline="true" class="qform">
      <el-form-item label="讲座名">
        <el-input v-model="query.title" placeholder="关键字" clearable style="width: 160px" @keyup.enter="getList" />
      </el-form-item>
      <el-form-item label="主讲人">
        <el-input v-model="query.lecturer" placeholder="关键字" clearable style="width: 130px" @keyup.enter="getList" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="query.lectureType" placeholder="全部" clearable style="width: 150px" @change="getList">
          <el-option v-for="t in types" :key="t.name" :label="`${t.name}（${t.cnt}）`" :value="t.name" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.stateFilter" placeholder="全部" clearable style="width: 110px" @change="getList">
          <el-option label="开放中" value="open" />
          <el-option label="已下架" value="gone" />
          <el-option label="已结束" value="ended" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="getList">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Download" :loading="collecting" @click="doCollect">立即采集</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button plain icon="Key" @click="cookieDialog = true">更新登录态</el-button>
      </el-col>
      <el-col :span="1.5" class="push-switch">
        <span class="lbl">讲座推送</span>
        <el-switch v-model="pushEnabled" :loading="pushSaving" inline-prompt
                   active-text="开" inactive-text="关" @change="togglePush" />
      </el-col>
      <el-col :span="1.5">
        <el-button plain icon="Tickets" @click="$router.push('/lecture/delivery')">推送记录</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <el-table v-loading="loading" :data="list" size="small">
      <el-table-column label="状态" width="86" align="center">
        <template #default="{ row }">
          <el-tag :type="stateTag(row.actState)" size="small">{{ stateText(row.actState) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="讲座" prop="title" min-width="220" show-overflow-tooltip />
      <el-table-column label="主讲人" prop="lecturer" width="110" show-overflow-tooltip />
      <el-table-column label="类型" prop="lectureType" width="120" />
      <el-table-column label="时间" width="170">
        <template #default="{ row }">
          <div>{{ row.openStart }}</div>
          <div class="dim">{{ row.openEnd }}</div>
        </template>
      </el-table-column>
      <el-table-column label="报名窗口" width="170">
        <template #default="{ row }">
          <div>{{ row.enrollStart }}</div>
          <div class="dim">{{ row.enrollEnd }}</div>
        </template>
      </el-table-column>
      <el-table-column label="名额" width="100" align="center">
        <template #default="{ row }">
          <span :class="full(row) ? 'full' : 'ok'">{{ row.enrollCount ?? '-' }}/{{ row.upperLimit ?? '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="地点" prop="place" min-width="150" show-overflow-tooltip />
      <el-table-column label="主办" prop="department" width="150" show-overflow-tooltip />
      <el-table-column label="操作" width="70" align="center">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total > 0" :total="total" v-model:page="query.pageNum" v-model:limit="query.pageSize" @pagination="getList" />

    <!-- 讲座详情 -->
    <el-dialog v-model="detailDialog" :title="detail.title || '讲座详情'" :width="'min(680px, 94vw)'" append-to-body>
      <div class="dmeta">
        <div><b>主讲：</b>{{ detail.lecturer || '-' }}</div>
        <div><b>主办：</b>{{ detail.department || '-' }}</div>
        <div><b>类型：</b>{{ detail.lectureType || '-' }}</div>
        <div><b>时间：</b>{{ detail.openStart }} ~ {{ detail.openEnd }}</div>
        <div><b>报名：</b>{{ detail.enrollStart }} ~ {{ detail.enrollEnd }}</div>
        <div><b>地点：</b>{{ detail.place || '-' }}</div>
        <div><b>名额：</b>{{ detail.enrollCount ?? '-' }}/{{ detail.upperLimit ?? '-' }}</div>
        <div><b>ID：</b>{{ detail.lectureId }}</div>
      </div>
      <el-divider content-position="left">讲座介绍</el-divider>
      <div class="dtext">{{ detail.contentText || '（教务系统没填）' }}</div>
      <el-divider content-position="left">主讲人介绍</el-divider>
      <div class="dtext">{{ detail.teacherText || '（教务系统没填）' }}</div>
    </el-dialog>

    <!-- 更新登录态 -->
    <el-dialog v-model="cookieDialog" title="更新教务登录态" :width="'min(640px, 94vw)'" append-to-body>
      <el-alert type="success" :closable="false" show-icon style="margin-bottom: 12px">
        <template #title>
          <b>贴 TGC</b>：一次登录能管很久，采集器会用它自动换会话，平时不用管。
        </template>
      </el-alert>
      <div class="howto">
        <div><b>1.</b> 浏览器打开 <code>https://i.jmu.edu.cn</code>，账号密码登录</div>
        <div><b>2.</b> F12 → <b>Application（应用）</b> → 左侧 <b>Cookies</b> → 点 <code>https://cas.paas.jmu.edu.cn</code></div>
        <div><b>3.</b> 找到 <b>TGC</b>，双击 Value 复制（一长串，100 多字符）</div>
        <div><b>4.</b> 粘到下面，点保存 → 自动试采集</div>
      </div>
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
        <template #title>
          没有 TGC？也可以贴 jwxt 的整行 Cookie（含 <code>__pstsid__</code> 和 <code>SESSION</code>），但那个 2 天就过期。
        </template>
      </el-alert>
      <el-input v-model="cookieText" type="textarea" :rows="5" placeholder="TGC 的值，或 __pstsid__=xxx; SESSION=yyy" />
      <template #footer>
        <el-button @click="cookieDialog = false">取消</el-button>
        <el-button type="primary" :loading="savingCookie" @click="saveCookie">保存并试采集</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Lecture">
import { ref, reactive, onMounted, computed } from 'vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const showSearch = ref(true)
const collecting = ref(false)
const savingCookie = ref(false)
const cookieDialog = ref(false)
const cookieText = ref('')
const pushEnabled = ref(false)
const pushSaving = ref(false)
const detailDialog = ref(false)
const detail = ref({})
const list = ref([])
const total = ref(0)
const types = ref([])
const stat = ref({})
const state = ref({})

const query = reactive({
  pageNum: 1,
  pageSize: 10,
  title: '',
  lecturer: '',
  lectureType: '',
  stateFilter: 'open'      // 默认只看开放中；已结束/已下架的由「消融」任务清理，想看历史可在筛选里切「全部」
})

const collectorOk = computed(() => state.value && state.value.ok === true)

function full(row) {
  return row.upperLimit != null && row.enrollCount != null && row.enrollCount >= row.upperLimit
}

function getList() {
  loading.value = true
  request({ url: '/system/lecture/list', method: 'get', params: query })
    .then(res => {
      list.value = res.rows || []
      total.value = res.total || 0
    })
    .catch(() => {})
    .finally(() => { loading.value = false })
}

function getStatus() {
  request({ url: '/system/lecture/status', method: 'get' })
    .then(res => {
      const d = (res && res.data) ? res.data : res
      types.value = d.types || []
      stat.value = d.stat || {}
      try {
        state.value = d.collector && d.collector.state ? JSON.parse(d.collector.state) : {}
      } catch (e) { state.value = {} }
    })
    .catch(() => {})
}

function resetQuery() {
  query.title = ''
  query.lecturer = ''
  query.lectureType = ''
  query.stateFilter = 'open'
  query.pageNum = 1
  getList()
}

function doCollect() {
  collecting.value = true
  request({ url: '/system/lecture/collect', method: 'post' })
    .then(res => {
      const d = (res && res.data) ? res.data : {}
      const log = (d.log || '').split('\n').filter(Boolean).slice(-4).join(' | ')
      ElMessage.success((res && res.msg) || '采集完成')
      if (log) ElMessage.info(log)
      getList(); getStatus()
    })
    .catch(err => {
      const m = (err && (err.msg || err.message)) || '采集失败'
      ElMessage.error(m)
      getStatus()
    })
    .finally(() => { collecting.value = false })
}

function saveCookie() {
  if (!cookieText.value || cookieText.value.trim().length < 20) {
    ElMessage.warning('先把 Cookie 整行贴进来')
    return
  }
  savingCookie.value = true
  request({ url: '/system/lecture/cookie', method: 'post', data: { cookie: cookieText.value } })
    .then(res => {
      ElMessage.success((res && res.msg) || '已更新')
      cookieDialog.value = false
      cookieText.value = ''
      doCollect()
    })
    .catch(err => {
      const m = (err && (err.msg || err.message)) || '保存失败'
      ElMessage.error(m)
    })
    .finally(() => { savingCookie.value = false })
}

function stateText(s) {
  return ({ open: '开放', gone: '已下架', ended: '已结束' })[s] || s || '-'
}

function stateTag(s) {
  return ({ open: 'success', gone: 'warning', ended: 'info' })[s] || 'info'
}

function openDetail(row) {
  detail.value = row || {}
  detailDialog.value = true
}

function loadPushConfig() {
  request({ url: '/system/lecture/push-config', method: 'get' })
    .then(res => {
      const d = (res && res.data) ? res.data : res
      pushEnabled.value = !!d.enabled
    })
    .catch(() => {})
}

function togglePush(v) {
  pushSaving.value = true
  request({ url: '/system/lecture/push-config', method: 'post', data: { enabled: v } })
    .then(res => { ElMessage.success((res && res.msg) || '已保存'); loadPushConfig() })
    .catch(err => {
      pushEnabled.value = !v
      ElMessage.error((err && (err.msg || err.message)) || '保存失败')
    })
    .finally(() => { pushSaving.value = false })
}

onMounted(() => { getList(); getStatus(); loadPushConfig() })
</script>

<style scoped>
.status-bar { margin-bottom: 14px; }
.push-switch { display: flex; align-items: center; gap: 8px; }
.push-switch .lbl { font-size: 13px; color: #606266; }
.dstat { margin-bottom: 10px; }
.dmeta { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 16px; font-size: 13px; color: #606266; }
.dmeta b { color: #303133; font-weight: 600; }
.dtext { font-size: 13px; line-height: 1.9; color: #606266; white-space: pre-wrap; word-break: break-word; max-height: 220px; overflow-y: auto; }
@media (max-width: 640px) { .dmeta { grid-template-columns: 1fr; } }
.qform { margin-bottom: 4px; }
.mb8 { margin-bottom: 8px; }
.dim { color: #a8abb2; font-size: 12px; }
.ok { color: #529b2e; }
.full { color: #c45656; font-weight: 600; }
.howto {
  background: #fafafa; border: 1px solid #ebeef5; border-radius: 8px;
  padding: 12px 14px; margin-bottom: 12px; font-size: 12.5px;
  color: #606266; line-height: 2;
}
.howto code { background: #f0f2f5; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
@media (max-width: 768px) {
  .qform :deep(.el-form-item) { margin-right: 8px; }
}
</style>
