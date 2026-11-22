<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="76px">
      <el-form-item label="活动标题" prop="title">
        <el-input v-model="queryParams.title" placeholder="关键词模糊匹配" clearable @keyup.enter="handleQuery" style="width: 190px" />
      </el-form-item>
      <el-form-item label="级别" prop="activityType">
        <el-select v-model="queryParams.activityType" placeholder="全部" clearable style="width: 110px">
          <el-option label="校级" value="school" />
          <el-option label="院级" value="yard" />
        </el-select>
      </el-form-item>
      <el-form-item label="主办学院" prop="deptLabel">
        <el-select v-model="queryParams.deptLabel" placeholder="全部" clearable filterable style="width: 210px">
          <el-option v-for="d in deptOptions" :key="d" :label="d" :value="d" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="actState">
        <el-select v-model="queryParams.actState" placeholder="全部" clearable style="width: 110px">
          <el-option label="开放中" value="open" />
          <el-option label="已结束" value="ended" />
        </el-select>
      </el-form-item>
      <el-form-item label="最低学分" prop="creditTotal">
        <el-input v-model="queryParams.creditTotal" placeholder="如 1" clearable @keyup.enter="handleQuery" style="width: 90px" />
      </el-form-item>
      <el-form-item label="活动时间">
        <el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD"
          range-separator="~" start-placeholder="起" end-placeholder="止" style="width: 230px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <!-- 活动由采集器写入；后台不提供增删改，避免被下次采集覆盖 -->
      <el-col :span="1.5">
        <el-button
          type="warning"
          plain
          icon="Download"
          @click="handleExport"
          v-hasPermi="['system:activity:export']"
        >导出</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="activityList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column label="活动标题" prop="title" :show-overflow-tooltip="true" min-width="230" />
      <el-table-column label="级别" align="center" width="84">
        <template #default="scope">
          <el-tag :type="scope.row.activityType === 'school' ? 'danger' : 'info'" size="small">
            {{ typeLabel(scope.row.activityType) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="学分" align="center" width="92">
        <template #default="scope">
          <span style="font-weight:600;color:#e6a23c">{{ creditText(scope.row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="活动时间" align="center" width="176">
        <template #default="scope">
          <div>{{ fmtTime(scope.row.startAt) }}</div>
          <div style="color:#909399;font-size:12px">至 {{ fmtTime(scope.row.endAt) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="报名窗口" align="center" width="176">
        <template #default="scope">
          <div style="font-size:12px;color:#606266">{{ fmtShort(scope.row.signinStart) }}</div>
          <div style="font-size:12px;color:#909399">~ {{ fmtShort(scope.row.signinEnd) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="主办学院" prop="deptLabel" :show-overflow-tooltip="true" width="150" />
      <el-table-column label="地点" prop="address" :show-overflow-tooltip="true" width="150" />
      <el-table-column label="名额" align="center" width="76">
        <template #default="scope">
          <span>{{ !scope.row.quota ? "不限" : scope.row.quota }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" align="center" width="86">
        <template #default="scope">
          <el-tag :type="scope.row.actState === 'open' ? 'success' : 'info'" size="small">
            {{ scope.row.actState === 'open' ? "开放中" : "已结束" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="首次发现" align="center" width="150">
        <template #default="scope">
          <span style="font-size:12px;color:#909399">{{ fmtTime(scope.row.firstSeen) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="84" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleView(scope.row)">详情</el-button>
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

    <!-- 活动详情（只读） -->
    <el-dialog :title="title" v-model="open" :width="'min(720px, 94vw)'" append-to-body>
      <el-descriptions :column="2" border size="default">
        <el-descriptions-item label="活动标题" :span="2">{{ form.title || "-" }}</el-descriptions-item>
        <el-descriptions-item label="级别">
          <el-tag :type="form.activityType === 'school' ? 'danger' : 'info'" size="small">
            {{ typeLabel(form.activityType) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="学分">
          <span style="font-weight:600;color:#e6a23c">{{ creditText(form) }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="活动时间" :span="2">
          {{ fmtTime(form.startAt) }} ~ {{ fmtTime(form.endAt) }}
        </el-descriptions-item>
        <el-descriptions-item label="报名窗口" :span="2">
          {{ fmtTime(form.signinStart) }} ~ {{ fmtTime(form.signinEnd) }}
        </el-descriptions-item>
        <el-descriptions-item label="主办学院">{{ form.deptLabel || "-" }}</el-descriptions-item>
        <el-descriptions-item label="地点">{{ form.address || "-" }}</el-descriptions-item>
        <el-descriptions-item label="名额">{{ !form.quota ? "不限" : form.quota }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="form.actState === 'open' ? 'success' : 'info'" size="small">
            {{ form.actState === "open" ? "开放中" : "已结束" }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="学分类别" :span="2">{{ form.creditTypeName || "-" }}</el-descriptions-item>
        <el-descriptions-item label="首次发现">{{ fmtTime(form.firstSeen) }}</el-descriptions-item>
        <el-descriptions-item label="最近同步">{{ fmtTime(form.lastSeen) }}</el-descriptions-item>
        <el-descriptions-item label="活动ID" :span="2">
          <span style="font-family:monospace;font-size:12px;color:#909399">{{ form.activityId }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="open = false">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Activity">
import { listActivity, deptOptions as deptOptionsApi } from "@/api/system/activity"

const { proxy } = getCurrentInstance()

const activityList = ref([])
const open = ref(false)
const loading = ref(true)
const showSearch = ref(true)
const ids = ref([])
const single = ref(true)
const multiple = ref(true)
const total = ref(0)
const title = ref("")
const dateRange = ref([])
const deptOptions = ref([])   // 主办学院下拉，从现有数据提取

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    title: undefined,
    activityType: undefined,
    activityTypeLabel: undefined,
    deptLabel: undefined,
    creatorCollege: undefined,
    creditTotal: undefined,
    creditDetail: undefined,
    creditTypeName: undefined,
    startAt: undefined,
    endAt: undefined,
    signinStart: undefined,
    signinEnd: undefined,
    signupWay: undefined,
    address: undefined,
    quota: undefined,
    actState: undefined,
    firstSeen: undefined,
    lastSeen: undefined,
    rawJson: undefined,
  },
  rules: {
  }
})

const { queryParams, form, rules } = toRefs(data)

// 学分展示：官网按档位发放（credit=该档学分，number=该档人数）。
// 分档显示区间，单档显示「最高 X」；credit_total 已是档位最高值，只作兜底。
function _trimNum(v) {
  const n = Number(v)
  return Number.isFinite(n) ? String(Number(n.toFixed(2))) : "-"
}
function creditText(row) {
  if (!row) return "-"
  const d = row.creditDetail
  if (d) {
    try {
      const arr = typeof d === "string" ? JSON.parse(d) : d
      const vals = (arr || [])
        .map((x) => Number(x && x.credit))
        .filter((v) => Number.isFinite(v))
      if (vals.length) {
        const lo = Math.min(...vals)
        const hi = Math.max(...vals)
        return lo === hi ? `最高 ${_trimNum(hi)}` : `${_trimNum(lo)}~${_trimNum(hi)}`
      }
    } catch (e) {
      /* 解析失败走兜底 */
    }
  }
  return row.creditTotal != null ? `最高 ${_trimNum(row.creditTotal)}` : "-"
}


/** 查询第二课堂活动列表 */
function getList() {
  loading.value = true
  listActivity(queryParams.value).then(response => {
    activityList.value = response.rows
    total.value = response.total
    loading.value = false
  })
}

/** 取消按钮 */
function cancel() {
  open.value = false
  reset()
}

/** 表单重置 */
function reset() {
  form.value = {
    activityId: null,
    title: null,
    activityType: null,
    activityTypeLabel: null,
    deptLabel: null,
    creatorCollege: null,
    creditTotal: null,
    creditDetail: null,
    creditTypeName: null,
    startAt: null,
    endAt: null,
    signinStart: null,
    signinEnd: null,
    signupWay: null,
    address: null,
    quota: null,
    actState: null,
    firstSeen: null,
    lastSeen: null,
    rawJson: null,
    createBy: null,
    createTime: null,
    updateBy: null,
    updateTime: null,
    remark: null
  }
  proxy.resetForm("queryRef")
}

/** 完整时间：YYYY-MM-DD HH:mm */
function fmtTime(v) {
  if (!v) return "-"
  const d = new Date(String(v).replace(/-/g, "/"))
  if (isNaN(d.getTime())) return String(v).slice(0, 16)
  const p = n => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** 短时间：MM-DD HH:mm */
function fmtShort(v) {
  if (!v) return "-"
  const t = fmtTime(v)
  return t.length > 15 ? t.slice(5) : t
}

/** 级别中文 */
function typeLabel(v) {
  return v === "school" ? "校级" : v === "yard" ? "院级" : (v || "-")
}

/** 详情弹窗 */
function handleView(row) {
  form.value = row
  open.value = true
  title.value = "活动详情"
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1
  queryParams.value.params = {}
  if (dateRange.value && dateRange.value.length === 2) {
    queryParams.value.params.beginStartAt = dateRange.value[0]
    queryParams.value.params.endStartAt = dateRange.value[1]
  }
  getList()
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef")
  dateRange.value = []
  handleQuery()
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.activityId)
  single.value = selection.length != 1
  multiple.value = !selection.length
}

/** 导出按钮操作 */
function handleExport() {
  proxy.download('system/activity/export', {
    ...queryParams.value
  }, `activity_${new Date().getTime()}.xlsx`)
}

/** 提取所有主办学院供下拉使用（新单位出现会自动纳入） */
function loadDeptOptions() {
  deptOptionsApi().then(res => {
    const arr = (res && res.data) ? res.data : (res || [])
    deptOptions.value = Array.isArray(arr)
      ? arr.filter(Boolean).sort((a, b) => String(a).localeCompare(String(b), 'zh-CN'))
      : []
  }).catch(() => {})
}

loadDeptOptions()
getList()
</script>
