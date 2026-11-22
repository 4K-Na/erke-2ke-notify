<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="76px">
      <el-form-item label="活动标题" prop="activityTitle">
        <el-input v-model="queryParams.activityTitle" placeholder="关键词" clearable @keyup.enter="handleQuery" style="width: 220px" />
      </el-form-item>
      <el-form-item label="创建时间">
        <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD"
          range-separator="~" start-placeholder="起" end-placeholder="止" style="width: 230px" />
      </el-form-item>
      <el-form-item label="只看失败">
        <el-switch v-model="onlyFailed" @change="handleQuery" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="warning" plain icon="Download" @click="handleExport" v-hasPermi="['system:delivery:export']">导出明细</el-button>
      </el-col>
      <el-col :span="1.5">
        <span style="line-height:32px;color:#909399;font-size:13px">
          一行一个活动 · 共 {{ total }} 个活动 · 本页明细 {{ totalRows }} 条
        </span>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="summaryList">
      <el-table-column label="活动" prop="activityTitle" min-width="280" show-overflow-tooltip>
        <template #default="scope">{{ scope.row.activityTitle || "-" }}</template>
      </el-table-column>
      <el-table-column label="级别" align="center" width="84">
        <template #default="scope">
          <el-tag size="small" :type="scope.row.activityType === 'school' ? 'danger' : 'info'" effect="plain">
            {{ scope.row.activityType === "school" ? "校级" : "院级" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="推送人数" align="center" width="104">
        <template #default="scope">
          <span style="font-weight:600">{{ scope.row.sentCnt }}/{{ scope.row.totalCnt }}</span>
        </template>
      </el-table-column>
      <el-table-column label="成功" align="center" width="76">
        <template #default="scope">
          <span style="color:#67c23a;font-weight:600">{{ scope.row.sentCnt }}</span>
        </template>
      </el-table-column>
      <el-table-column label="失败" align="center" width="76">
        <template #default="scope">
          <span :style="{ color: Number(scope.row.failedCnt) > 0 ? '#f56c6c' : '#c0c4cc', fontWeight: 600 }">
            {{ scope.row.failedCnt }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="待发" align="center" width="72">
        <template #default="scope">
          <span :style="{ color: Number(scope.row.pendingCnt) > 0 ? '#e6a23c' : '#c0c4cc' }">{{ scope.row.pendingCnt }}</span>
        </template>
      </el-table-column>
      <el-table-column label="最近推送" align="center" width="160">
        <template #default="scope">
          <span style="font-size:12px">{{ fmtTime(scope.row.lastSentTime || scope.row.lastCreateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="88" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="openDetail(scope.row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total>0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <!-- 单个活动的投递明细 -->
    <el-dialog v-model="detailOpen" :title="detailTitle" :width="'min(860px, 94vw)'" append-to-body>
      <el-table :data="detailList" v-loading="detailLoading" size="small" max-height="440">
        <el-table-column label="订阅者" width="150">
          <template #default="scope">{{ scope.row.subscriberName || ("#" + scope.row.subscriberId) }}</template>
        </el-table-column>
        <el-table-column label="状态" align="center" width="96">
          <template #default="scope">
            <el-tag size="small" :type="statusTagType(scope.row.sendStatus)">{{ statusLabel(scope.row.sendStatus) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="尝试" align="center" width="70">
          <template #default="scope">
            <span :style="{ color: scope.row.attempt > 0 ? '#e6a23c' : '#909399' }">{{ scope.row.attempt ?? 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="通道" align="center" width="96">
          <template #default="scope">
            <el-tag size="small" :type="channelTagType(scope.row.channel)" effect="plain">{{ channelLabel(scope.row.channel) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="失败原因" show-overflow-tooltip min-width="180">
          <template #default="scope">
            <span style="font-size:12px;color:#f56c6c">{{ scope.row.lastError || "" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="发送时间" align="center" width="150">
          <template #default="scope">
            <span style="font-size:12px">{{ fmtTime(scope.row.sentTime) }}</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="detailOpen = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Delivery">
import { summaryDelivery, listDelivery } from "@/api/system/delivery"

const { proxy } = getCurrentInstance()

const summaryList = ref([])
const detailList = ref([])
const detailOpen = ref(false)
const detailLoading = ref(false)
const detailTitle = ref("")
const onlyFailed = ref(false)
const loading = ref(false)
const showSearch = ref(true)
const total = ref(0)
const totalRows = ref(0)
const dateRange = ref([])

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 20,
    activityTitle: undefined,
    params: {}
  }
})

const { queryParams } = toRefs(data)

/** 聚合列表 */
function getList() {
  loading.value = true
  const q = { ...queryParams.value }
  q.params = { ...(q.params || {}) }
  if (onlyFailed.value) q.params.onlyFailed = "1"
  summaryDelivery(q).then(response => {
    summaryList.value = response.rows || []
    total.value = response.total || 0
    totalRows.value = (response.rows || []).reduce((s, r) => s + Number(r.totalCnt || 0), 0)
    loading.value = false
  }).catch(() => { loading.value = false })
}

/** 打开某活动的明细 */
function openDetail(row) {
  detailTitle.value = row.activityTitle || "投递明细"
  detailOpen.value = true
  detailLoading.value = true
  detailList.value = []
  const q = { pageNum: 1, pageSize: 200, activityId: row.activityId }
  if (onlyFailed.value) q.sendStatus = "failed"
  listDelivery(q).then(response => {
    detailList.value = response.rows || []
    detailLoading.value = false
  }).catch(() => { detailLoading.value = false })
}

/** 时间格式化 */
function fmtTime(v) {
  if (!v) return "-"
  const d = new Date(String(v).replace(/-/g, "/"))
  if (isNaN(d.getTime())) return String(v).slice(0, 16)
  const p = n => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function channelLabel(v) {
  return { wxpusher: "微信推送", wecom: "企业微信", email: "邮件" }[v] || (v || "-")
}
function channelTagType(v) {
  return { wxpusher: "success", wecom: "primary", email: "info" }[v] || "info"
}
function statusLabel(v) {
  return { pending: "待发送", sent: "已发送", failed: "失败" }[v] || (v || "-")
}
function statusTagType(v) {
  return { pending: "warning", sent: "success", failed: "danger" }[v] || "info"
}

/** 搜索 */
function handleQuery() {
  queryParams.value.pageNum = 1
  queryParams.value.params = {}
  if (dateRange.value && dateRange.value.length === 2) {
    queryParams.value.params.beginCreateTime = dateRange.value[0]
    queryParams.value.params.endCreateTime = dateRange.value[1]
  }
  getList()
}

/** 重置 */
function resetQuery() {
  proxy.resetForm("queryRef")
  dateRange.value = []
  onlyFailed.value = false
  handleQuery()
}

/** 导出明细 */
function handleExport() {
  const q = { ...queryParams.value }
  if (onlyFailed.value) q.sendStatus = "failed"
  proxy.download("system/delivery/export", q, `delivery_${new Date().getTime()}.xlsx`)
}

getList()
</script>
