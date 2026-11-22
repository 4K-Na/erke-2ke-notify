<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="级别名称" prop="activityTypeLabel">
        <el-input
          v-model="queryParams.activityTypeLabel"
          placeholder="请输入级别名称"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="主办学院" prop="deptLabel">
        <el-input
          v-model="queryParams.deptLabel"
          placeholder="请输入主办学院"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="创建学院" prop="creatorCollege">
        <el-input
          v-model="queryParams.creatorCollege"
          placeholder="请输入创建学院"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="总学分" prop="creditTotal">
        <el-input
          v-model="queryParams.creditTotal"
          placeholder="请输入总学分"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="学分类别" prop="creditTypeName">
        <el-input
          v-model="queryParams.creditTypeName"
          placeholder="请输入学分类别"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="开始时间" prop="startAt">
        <el-date-picker clearable
          v-model="queryParams.startAt"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="请选择开始时间">
        </el-date-picker>
      </el-form-item>
      <el-form-item label="结束时间" prop="endAt">
        <el-date-picker clearable
          v-model="queryParams.endAt"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="请选择结束时间">
        </el-date-picker>
      </el-form-item>
      <el-form-item label="报名开始" prop="signinStart">
        <el-date-picker clearable
          v-model="queryParams.signinStart"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="请选择报名开始">
        </el-date-picker>
      </el-form-item>
      <el-form-item label="报名截止" prop="signinEnd">
        <el-date-picker clearable
          v-model="queryParams.signinEnd"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="请选择报名截止">
        </el-date-picker>
      </el-form-item>
      <el-form-item label="报名方式" prop="signupWay">
        <el-input
          v-model="queryParams.signupWay"
          placeholder="请输入报名方式"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="活动地点" prop="address">
        <el-input
          v-model="queryParams.address"
          placeholder="请输入活动地点"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="名额" prop="quota">
        <el-input
          v-model="queryParams.quota"
          placeholder="请输入名额"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="状态 open/ended" prop="actState">
        <el-input
          v-model="queryParams.actState"
          placeholder="请输入状态 open/ended"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="首次发现" prop="firstSeen">
        <el-date-picker clearable
          v-model="queryParams.firstSeen"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="请选择首次发现">
        </el-date-picker>
      </el-form-item>
      <el-form-item label="最近同步" prop="lastSeen">
        <el-date-picker clearable
          v-model="queryParams.lastSeen"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="请选择最近同步">
        </el-date-picker>
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
          v-hasPermi="['system:activity:add']"
        >新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
          v-hasPermi="['system:activity:edit']"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
          v-hasPermi="['system:activity:remove']"
        >删除</el-button>
      </el-col>
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
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="2ke活动ID" align="center" prop="activityId" />
      <el-table-column label="活动标题" align="center" prop="title" />
      <el-table-column label="级别 yard/school" align="center" prop="activityType" />
      <el-table-column label="级别名称" align="center" prop="activityTypeLabel" />
      <el-table-column label="主办学院" align="center" prop="deptLabel" />
      <el-table-column label="创建学院" align="center" prop="creatorCollege" />
      <el-table-column label="总学分" align="center" prop="creditTotal" />
      <el-table-column label="学分明细JSON" align="center" prop="creditDetail" />
      <el-table-column label="学分类别" align="center" prop="creditTypeName" />
      <el-table-column label="开始时间" align="center" prop="startAt" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.startAt, '{y}-{m}-{d}') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="结束时间" align="center" prop="endAt" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.endAt, '{y}-{m}-{d}') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="报名开始" align="center" prop="signinStart" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.signinStart, '{y}-{m}-{d}') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="报名截止" align="center" prop="signinEnd" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.signinEnd, '{y}-{m}-{d}') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="报名方式" align="center" prop="signupWay" />
      <el-table-column label="活动地点" align="center" prop="address" />
      <el-table-column label="名额" align="center" prop="quota" />
      <el-table-column label="状态 open/ended" align="center" prop="actState" />
      <el-table-column label="首次发现" align="center" prop="firstSeen" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.firstSeen, '{y}-{m}-{d}') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="最近同步" align="center" prop="lastSeen" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.lastSeen, '{y}-{m}-{d}') }}</span>
        </template>
      </el-table-column>
      <el-table-column label="原始JSON" align="center" prop="rawJson" />
      <el-table-column label="备注" align="center" prop="remark" />
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:activity:edit']">修改</el-button>
          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['system:activity:remove']">删除</el-button>
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

    <!-- 添加或修改第二课堂活动对话框 -->
    <el-dialog :title="title" v-model="open" width="500px" append-to-body>
      <el-form ref="activityRef" :model="form" :rules="rules" label-width="100px">
        <el-row>
          <el-col :span="24">
            <el-form-item label="活动标题" prop="title">
              <el-input v-model="form.title" type="textarea" placeholder="请输入内容" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="级别名称" prop="activityTypeLabel">
              <el-input v-model="form.activityTypeLabel" placeholder="请输入级别名称" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="主办学院" prop="deptLabel">
              <el-input v-model="form.deptLabel" placeholder="请输入主办学院" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="创建学院" prop="creatorCollege">
              <el-input v-model="form.creatorCollege" placeholder="请输入创建学院" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="总学分" prop="creditTotal">
              <el-input v-model="form.creditTotal" placeholder="请输入总学分" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="学分明细JSON" prop="creditDetail">
              <el-input v-model="form.creditDetail" type="textarea" placeholder="请输入内容" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="学分类别" prop="creditTypeName">
              <el-input v-model="form.creditTypeName" placeholder="请输入学分类别" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="开始时间" prop="startAt">
              <el-date-picker clearable
                v-model="form.startAt"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="请选择开始时间">
              </el-date-picker>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="结束时间" prop="endAt">
              <el-date-picker clearable
                v-model="form.endAt"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="请选择结束时间">
              </el-date-picker>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="报名开始" prop="signinStart">
              <el-date-picker clearable
                v-model="form.signinStart"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="请选择报名开始">
              </el-date-picker>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="报名截止" prop="signinEnd">
              <el-date-picker clearable
                v-model="form.signinEnd"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="请选择报名截止">
              </el-date-picker>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="报名方式" prop="signupWay">
              <el-input v-model="form.signupWay" placeholder="请输入报名方式" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="活动地点" prop="address">
              <el-input v-model="form.address" placeholder="请输入活动地点" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="名额" prop="quota">
              <el-input v-model="form.quota" placeholder="请输入名额" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="状态 open/ended" prop="actState">
              <el-input v-model="form.actState" placeholder="请输入状态 open/ended" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="首次发现" prop="firstSeen">
              <el-date-picker clearable
                v-model="form.firstSeen"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="请选择首次发现">
              </el-date-picker>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="最近同步" prop="lastSeen">
              <el-date-picker clearable
                v-model="form.lastSeen"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="请选择最近同步">
              </el-date-picker>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="原始JSON" prop="rawJson">
              <el-input v-model="form.rawJson" type="textarea" placeholder="请输入内容" />
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

<script setup name="Activity">
import { listActivity, getActivity, delActivity, addActivity, updateActivity } from "@/api/system/activity"

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
  proxy.resetForm("activityRef")
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
  ids.value = selection.map(item => item.activityId)
  single.value = selection.length != 1
  multiple.value = !selection.length
}

/** 新增按钮操作 */
function handleAdd() {
  reset()
  open.value = true
  title.value = "添加第二课堂活动"
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset()
  const _activityId = row.activityId || ids.value
  getActivity(_activityId).then(response => {
    form.value = response.data
    open.value = true
    title.value = "修改第二课堂活动"
  })
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["activityRef"].validate(valid => {
    if (valid) {
      if (form.value.activityId != null) {
        updateActivity(form.value).then(() => {
          proxy.$modal.msgSuccess("修改成功")
          open.value = false
          getList()
        })
      } else {
        addActivity(form.value).then(() => {
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
  const _activityIds = row.activityId || ids.value
  proxy.$modal.confirm('是否确认删除第二课堂活动编号为"' + _activityIds + '"的数据项？').then(function() {
    return delActivity(_activityIds)
  }).then(() => {
    getList()
    proxy.$modal.msgSuccess("删除成功")
  }).catch(() => {})
}

/** 导出按钮操作 */
function handleExport() {
  proxy.download('system/activity/export', {
    ...queryParams.value
  }, `activity_${new Date().getTime()}.xlsx`)
}

getList()
</script>
