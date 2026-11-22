<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="标题" prop="title">
        <el-input v-model="queryParams.title" placeholder="标题关键字" clearable style="width: 170px" @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item label="置顶" prop="pinned">
        <el-select v-model="queryParams.pinned" placeholder="全部" clearable style="width: 100px">
          <el-option label="置顶" value="1" />
          <el-option label="不置顶" value="0" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="全部" clearable style="width: 100px">
          <el-option label="显示" value="0" />
          <el-option label="隐藏" value="1" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
          type="primary"
          plain
          icon="Plus"
          @click="handleAdd"
          v-hasPermi="['system:notice:add']"
        >新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['system:notice:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['system:notice:remove']"
        >删除</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="warning"
          plain
          icon="Download"
          @click="handleExport"
          v-hasPermi="['system:notice:export']"
        >导出</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="noticeList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="50" align="center" />
      <el-table-column label="ID" align="center" prop="noticeId" width="70" />
      <el-table-column label="标题" align="left" prop="title" min-width="180" show-overflow-tooltip />
      <el-table-column label="正文" align="left" prop="content" min-width="260" show-overflow-tooltip>
        <template #default="scope">
          <span class="content-cell">{{ (scope.row.content || '').replace(/\n/g, '  ') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="置顶" align="center" width="76">
        <template #default="scope">
          <el-tag v-if="scope.row.pinned === '1'" type="primary" effect="plain" size="small">置顶</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="生效" align="center" prop="validFrom" width="150">
        <template #default="scope">
          <span v-if="scope.row.validFrom">{{ fmtTime(scope.row.validFrom) }}</span>
          <span v-else class="muted">即时</span>
        </template>
      </el-table-column>
      <el-table-column label="失效" align="center" prop="validTo" width="150">
        <template #default="scope">
          <span v-if="scope.row.validTo">{{ fmtTime(scope.row.validTo) }}</span>
          <span v-else class="muted">长期</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" align="center" width="76">
        <template #default="scope">
          <el-tag :type="scope.row.status === '0' ? 'success' : 'info'" effect="plain" size="small">
            {{ scope.row.status === '0' ? '显示' : '隐藏' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="排序" align="center" prop="sortNo" width="66" />
      <el-table-column label="操作" align="center" width="150" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:tnotice:edit']">修改</el-button>
          <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['system:tnotice:remove']">删除</el-button>
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

    <!-- 添加或修改公告对话框 -->
    <el-dialog :title="title" v-model="open" :width="'min(500px, 94vw)'" append-to-body>
      <el-form ref="noticeRef" :model="form" :rules="rules" label-width="100px">
        <el-row>
          <el-col :span="24">
            <el-form-item label="标题" prop="title">
              <el-input v-model="form.title" placeholder="请输入标题" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="正文">
              <editor v-model="form.content" :min-height="192"/>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="置顶" prop="pinned">
              <el-switch v-model="form.pinned" active-value="1" inactive-value="0" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="生效时间" prop="validFrom">
              <el-date-picker clearable
                v-model="form.validFrom"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                placeholder="请选择生效时间">
              </el-date-picker>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="失效时间" prop="validTo">
              <el-date-picker clearable
                v-model="form.validTo"
                type="datetime"
                value-format="YYYY-MM-DD HH:mm:ss"
                placeholder="请选择失效时间">
              </el-date-picker>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="排序" prop="sortNo">
              <el-input v-model="form.sortNo" placeholder="请输入排序" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注" prop="remark">
              <el-input v-model="form.remark" type="textarea" placeholder="请输入内容" />
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

<script setup name="Notice">
import { listNotice, getNotice, delNotice, addNotice, updateNotice } from "@/api/system/tnotice"

const { proxy } = getCurrentInstance()

const noticeList = ref([])
const open = ref(false)
const loading = ref(true)
const showSearch = ref(true)
const ids = ref([])
const single = ref(true)
const multiple = ref(true)
const total = ref(0)
const title = ref("")

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    title: undefined,
    content: undefined,
    pinned: undefined,
    validFrom: undefined,
    validTo: undefined,
    status: undefined,
    sortNo: undefined,
  },
  rules: {
    title: [
      { required: true, message: "标题不能为空", trigger: "blur" }
    ],
  }
})

const { queryParams, form, rules } = toRefs(data)

/** 查询公告列表 */
function fmtTime(v) {
  if (!v) return ''
  var d = new Date(String(v).replace(/-/g, '/'))
  if (isNaN(d.getTime())) return String(v).slice(0, 16)
  var p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function getList() {
  loading.value = true
  listNotice(queryParams.value).then(response => {
    noticeList.value = response.rows
    total.value = response.total
  }).catch(() => {}).finally(() => { loading.value = false })
}

/** 取消按钮 */
function cancel() {
  open.value = false
  reset()
}

/** 表单重置 */
function reset() {
  form.value = {
    noticeId: null,
    title: null,
    content: null,
    pinned: null,
    validFrom: null,
    validTo: null,
    status: null,
    sortNo: null,
    createBy: null,
    createTime: null,
    updateBy: null,
    updateTime: null,
    remark: null
  }
  proxy.resetForm("noticeRef")
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef")
  handleQuery()
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.noticeId)
  single.value = selection.length != 1
  multiple.value = !selection.length
}

/** 新增按钮操作 */
function handleAdd() {
  reset()
  open.value = true
  title.value = "添加公告"
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset()
  const _noticeId = row.noticeId || ids.value
  getNotice(_noticeId).then(response => {
    form.value = response.data
    open.value = true
    title.value = "修改公告"
  })
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["noticeRef"].validate(valid => {
    if (valid) {
      if (form.value.noticeId != null) {
        updateNotice(form.value).then(() => {
          proxy.$modal.msgSuccess("修改成功")
          open.value = false
          getList()
        })
      } else {
        addNotice(form.value).then(() => {
          proxy.$modal.msgSuccess("新增成功")
          open.value = false
          getList()
        })
      }
    }
  })
}

/** 删除按钮操作 */
function handleDelete(row) {
  const _noticeIds = row.noticeId || ids.value
  proxy.$modal.confirm('是否确认删除公告编号为"' + _noticeIds + '"的数据项？').then(function() {
    return delNotice(_noticeIds)
  }).then(() => {
    getList()
    proxy.$modal.msgSuccess("删除成功")
  }).catch(() => {})
}

/** 导出按钮操作 */
function handleExport() {
  proxy.download('system/tnotice/export', {
    ...queryParams.value
  }, `notice_${new Date().getTime()}.xlsx`)
}

getList()
</script>

<style scoped>
.content-cell { color: #606266; font-size: 13px; }
.muted { color: #c0c4cc; font-size: 12px; }
</style>
