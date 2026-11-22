<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="76px">
      <el-form-item label="订阅者" prop="nickname">
        <el-input v-model="queryParams.nickname" placeholder="昵称/姓名" clearable @keyup.enter="handleQuery" style="width: 150px" />
      </el-form-item>
      <el-form-item label="班级" prop="className">
        <el-input v-model="queryParams.className" placeholder="班级" clearable @keyup.enter="handleQuery" style="width: 150px" />
      </el-form-item>
      <el-form-item label="通道" prop="channel">
        <el-select v-model="queryParams.channel" placeholder="全部" clearable style="width: 130px">
          <el-option label="企业微信" value="wecom" />
          <el-option label="微信推送" value="wxpusher" />
          <el-option label="邮件" value="email" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="全部" clearable style="width: 110px">
          <el-option label="正常" value="0" />
          <el-option label="停用" value="1" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd" v-hasPermi="['system:subscriber:add']">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="success" plain icon="Edit" :disabled="single" @click="handleUpdate" v-hasPermi="['system:subscriber:edit']">修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="danger" plain icon="Delete" :disabled="multiple" @click="handleDelete" v-hasPermi="['system:subscriber:remove']">删除</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="warning" plain icon="Download" @click="handleExport" v-hasPermi="['system:subscriber:export']">导出</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="subscriberList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column label="订阅者" min-width="150">
        <template #default="scope">
          <div class="sub-cell">
            <span class="sub-name">{{ scope.row.nickname || scope.row.realName || '-' }}</span>
            <span class="sub-id">{{ scope.row.externalId }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="班级" prop="className" :show-overflow-tooltip="true" width="130">
        <template #default="scope">{{ scope.row.className || '-' }}</template>
      </el-table-column>
      <el-table-column label="接收通道" align="center" width="100">
        <template #default="scope">
          <el-tag :type="channelTagType(scope.row.channel)" effect="plain" size="small">{{ channelLabel(scope.row.channel) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="过滤规则" min-width="240">
        <template #default="scope">
          <div class="rule-cell" v-if="hasRule(scope.row)">
            <el-tag v-for="k in splitKeywords(scope.row.keywords)" :key="k" size="small" effect="plain" class="rule-tag">{{ k }}</el-tag>
            <el-tag v-if="scope.row.onlySchool === '1'" size="small" type="danger" effect="plain" class="rule-tag">仅校级</el-tag>
          </div>
          <span v-else class="muted">全部活动</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" align="center" width="80">
        <template #default="scope">
          <el-switch v-model="scope.row.status" active-value="0" inactive-value="1" @change="handleStatusChange(scope.row)" />
        </template>
      </el-table-column>
      <el-table-column label="加入时间" align="center" width="140">
        <template #default="scope">{{ fmtTime(scope.row.createTime) }}</template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="90" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:subscriber:edit']">修改</el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination v-show="total > 0" :total="total" v-model:page="queryParams.pageNum" v-model:limit="queryParams.pageSize" @pagination="getList" />

    <!-- 表单 -->
    <el-dialog :title="title" v-model="open" :width="'min(580px, 94vw)'" append-to-body>
      <el-form ref="subscriberRef" :model="form" :rules="rules" label-width="92px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="接收通道" prop="channel">
              <el-select v-model="form.channel" placeholder="选择通道" style="width: 100%">
                <el-option label="企业微信" value="wecom" />
                <el-option label="微信推送" value="wxpusher" />
                <el-option label="邮件" value="email" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="外部ID" prop="externalId">
              <el-input v-model="form.externalId" placeholder="企业微信 userid" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="昵称" prop="nickname">
              <el-input v-model="form.nickname" placeholder="显示名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="真实姓名" prop="realName">
              <el-input v-model="form.realName" placeholder="真实姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="班级" prop="className">
              <el-input v-model="form.className" placeholder="如 机械2511" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-radio-group v-model="form.status">
                <el-radio value="0">正常</el-radio>
                <el-radio value="1">停用</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>

          <el-col :span="24">
            <el-divider content-position="left">推送规则（留空表示接收全部活动）</el-divider>
          </el-col>

          <el-col :span="24">
            <el-form-item label="关键词">
              <el-select
                v-model="keywordTags"
                multiple
                filterable
                allow-create
                default-first-option
                :reserve-keyword="false"
                placeholder="输入后回车添加，如：志愿、讲座、比赛"
                style="width: 100%">
                <el-option v-for="k in keywordSuggest" :key="k" :label="k" :value="k" />
              </el-select>
              <div class="hint">活动标题包含任一关键词才会推送</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="只看校级">
              <el-switch v-model="onlySchoolBool" active-text="是" inactive-text="否" inline-prompt />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注" prop="remark">
              <el-input v-model="form.remark" type="textarea" :rows="2" placeholder="可选" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" @click="submitForm">确 定</el-button>
          <el-button @click="cancel">取 消</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Subscriber">
import { listSubscriber, getSubscriber, delSubscriber, addSubscriber, updateSubscriber } from "@/api/system/subscriber"

const { proxy } = getCurrentInstance()

const subscriberList = ref([])
const open = ref(false)
const loading = ref(true)
const showSearch = ref(true)
const ids = ref([])
const single = ref(true)
const multiple = ref(true)
const total = ref(0)
const title = ref("")

// 表单的辅助状态：关键词标签、只看校级开关
const keywordTags = ref([])
const onlySchoolBool = ref(false)

const keywordSuggest = ["志愿", "讲座", "比赛", "培训", "晚会", "运动会", "献血", "招聘", "社团", "实践"]

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    channel: undefined,
    externalId: undefined,
    nickname: undefined,
    realName: undefined,
    className: undefined,
    keywords: undefined,
    onlySchool: undefined,
    status: undefined,
  },
  rules: {
    channel: [{ required: true, message: "请选择接收通道", trigger: "change" }],
    externalId: [{ required: true, message: "外部ID不能为空", trigger: "blur" }],
  }
})

const { queryParams, form, rules } = toRefs(data)

function getList() {
  loading.value = true
  listSubscriber(queryParams.value).then(response => {
    subscriberList.value = response.rows
    total.value = response.total
  }).catch(() => {}).finally(() => { loading.value = false })
}

function cancel() {
  open.value = false
  reset()
}

function reset() {
  form.value = {
    subscriberId: null,
    channel: "wecom",
    externalId: null,
    nickname: null,
    realName: null,
    className: null,
    keywords: null,
    onlySchool: "0",
    status: "0",
    remark: null
  }
  keywordTags.value = []
  onlySchoolBool.value = false
  proxy.resetForm("subscriberRef")
}

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

function splitKeywords(v) {
  if (!v) return []
  return String(v).split(/[,，]/).map(s => s.trim()).filter(Boolean)
}

function hasRule(row) {
  return !!(row.keywords || row.onlySchool === "1")
}

function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

function resetQuery() {
  proxy.resetForm("queryRef")
  handleQuery()
}

function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.subscriberId)
  single.value = selection.length != 1
  multiple.value = !selection.length
}

function handleAdd() {
  reset()
  open.value = true
  title.value = "添加订阅者"
}

function handleUpdate(row) {
  reset()
  const _subscriberId = row.subscriberId || ids.value
  getSubscriber(_subscriberId).then(response => {
    const d = response.data
    form.value = d
    form.value.status = d.status || "0"
    form.value.channel = d.channel || "wecom"
    // 回填辅助控件
    keywordTags.value = splitKeywords(d.keywords)
    onlySchoolBool.value = d.onlySchool === "1"
    open.value = true
    title.value = "修改订阅者"
  })
}

function submitForm() {
  proxy.$refs["subscriberRef"].validate(valid => {
    if (!valid) return
    // 把辅助控件合并回 form
    form.value.keywords = keywordTags.value.length ? keywordTags.value.join(",") : null
    form.value.onlySchool = onlySchoolBool.value ? "1" : "0"

    const done = () => { open.value = false; getList() }
    if (form.value.subscriberId != null) {
      updateSubscriber(form.value).then(() => { proxy.$modal.msgSuccess("修改成功"); done() })
    } else {
      addSubscriber(form.value).then(() => { proxy.$modal.msgSuccess("新增成功"); done() })
    }
  })
}

function handleStatusChange(row) {
  updateSubscriber(row).then(() => {
    proxy.$modal.msgSuccess(row.status === "0" ? "已启用" : "已停用")
  }).catch(() => { getList() })
}

function handleDelete(row) {
  const _subscriberIds = row.subscriberId || ids.value
  proxy.$modal.confirm('确认删除选中的 ' + _subscriberIds.length + ' 个订阅者？').then(function () {
    return delSubscriber(_subscriberIds)
  }).then(() => {
    getList()
    proxy.$modal.msgSuccess("删除成功")
  }).catch(() => {})
}

function handleExport() {
  proxy.download('system/subscriber/export', {
    ...queryParams.value
  }, `subscriber_${new Date().getTime()}.xlsx`)
}

getList()
</script>

<style scoped>
.sub-cell { display: flex; flex-direction: column; line-height: 1.35; }
.sub-name { font-size: 13px; color: #303133; }
.sub-id { font-size: 11px; color: #a8abb2; }
.rule-cell { display: flex; flex-wrap: wrap; gap: 4px; }
.rule-tag { margin: 0; }
.muted { color: #c0c4cc; font-size: 12px; }
.hint { font-size: 11px; color: #a8abb2; line-height: 1.5; margin-top: 2px; }
</style>
