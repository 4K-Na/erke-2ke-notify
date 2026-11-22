<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <div class="refresh-bar">
      <span class="refresh-hint">数据每分钟自动刷新 · 最后更新 {{ lastUpdate || '—' }}</span>
      <el-link type="primary" :underline="false" @click="loadAll">立即刷新</el-link>
    </div>

    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="8" :md="4" v-for="c in cards" :key="c.label">
        <div class="stat-card" :class="c.theme">
          <div class="stat-value">{{ c.value }}</div>
          <div class="stat-label">{{ c.label }}</div>
        </div>
      </el-col>
    </el-row>

    <!-- 趋势图 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :lg="14">
        <el-card class="panel" shadow="never">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">最近 7 天推送</span>
              <span class="panel-sub">成功 {{ chartSum.ok }} · 失败 {{ chartSum.fail }}（基于最近 {{ sampledCount }} 条）</span>
            </div>
          </template>
          <div ref="pushChartRef" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="10">
        <el-card class="panel" shadow="never">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">订阅者增长</span>
              <span class="panel-sub">累计 {{ cards[2].value }}</span>
            </div>
          </template>
          <div ref="subChartRef" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 最新活动 -->
      <el-col :xs="24" :lg="14">
        <el-card class="panel" shadow="never">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">最新开放活动</span>
              <el-link type="primary" :underline="false" @click="$router.push('/2ke/activity')">查看全部</el-link>
            </div>
          </template>
          <el-table :data="activities" size="small" v-loading="loading.act" empty-text="暂无开放活动">
            <el-table-column prop="title" label="活动名称" min-width="200" show-overflow-tooltip />
            <el-table-column label="级别" width="70" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="row.activityType === 'school' ? 'danger' : 'info'" effect="plain">
                  {{ row.activityType === 'school' ? '校级' : '院级' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="学分" width="78" align="center">
              <template #default="{ row }">
                <span style="font-weight:600;color:#e6a23c">{{ creditText(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="开始时间" width="130" align="center">
              <template #default="{ row }">{{ (row.startAt || '').slice(5, 16) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 最近投递 -->
      <el-col :xs="24" :lg="10">
        <el-card class="panel" shadow="never">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">最近推送</span>
              <el-link type="primary" :underline="false" @click="$router.push('/2ke/delivery')">查看全部</el-link>
            </div>
          </template>
          <el-table :data="deliveries" size="small" v-loading="loading.del" empty-text="还没有推送记录">
            <el-table-column prop="activityTitle" label="活动" min-width="150" show-overflow-tooltip />
            <el-table-column prop="subscriberName" label="接收人" width="86" show-overflow-tooltip />
            <el-table-column label="状态" width="76" align="center">
              <template #default="{ row }">
                <el-tag size="small" :type="statusType(row.sendStatus)" effect="plain">
                  {{ statusText(row.sendStatus) }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 运行说明 -->
    <el-card class="panel tip" shadow="never">
      <div class="tip-grid">
        <div class="tip-item">
          <div class="tip-k">采集频率</div>
          <div class="tip-v">每 8 分钟</div>
        </div>
        <div class="tip-item">
          <div class="tip-k">推送频率</div>
          <div class="tip-v">每 5 分钟</div>
        </div>
        <div class="tip-item">
          <div class="tip-k">订阅入口</div>
          <div class="tip-v"><a href="https://example.com/" target="_blank">example.com</a></div>
        </div>
        <div class="tip-item">
          <div class="tip-k">异常告警</div>
          <div class="tip-v">采集停 40 分钟 → 微信通知</div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup name="Index">
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { listActivity } from '@/api/system/activity'
import { listDelivery } from '@/api/system/delivery'
import { listSubscriber } from '@/api/system/subscriber'
import request from '@/utils/request'

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const loading = reactive({ act: false, del: false })
const activities = ref([])
const deliveries = ref([])
const cards = ref([
  { label: '开放中活动', value: '-', theme: 'blue' },
  { label: '活动总数', value: '-', theme: 'green' },
  { label: '订阅者', value: '-', theme: 'purple' },
  { label: '已推送', value: '-', theme: 'orange' },
  { label: '讲座', value: '-', theme: 'blue' },
  { label: '讲座可报', value: '-', theme: 'green' }
])

const pushChartRef = ref(null)
const subChartRef = ref(null)
let pushChart = null
let subChart = null

const chartSum = reactive({ ok: 0, fail: 0 })
const sampledCount = ref(0)
const lastUpdate = ref('')
let refreshTimer = null
const REFRESH_MS = 60000        // 每分钟自动刷新

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

function statusType(s) {
  return { sent: 'success', failed: 'danger', pending: 'warning' }[s] || 'info'
}
function statusText(s) {
  return { sent: '已发送', failed: '失败', pending: '待发' }[s] || s
}

/** 最近 n 天的日期数组，格式 MM-DD */
function lastDays(n) {
  const out = []
  const now = new Date()
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now.getTime() - i * 86400000)
    const p = x => String(x).padStart(2, '0')
    out.push({ key: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`, label: `${p(d.getMonth() + 1)}-${p(d.getDate())}` })
  }
  return out
}

function renderPushChart(rows) {
  sampledCount.value = (rows || []).length
  if (!pushChartRef.value) return
  const days = lastDays(7)
  const okMap = {}, failMap = {}
  rows.forEach(r => {
    const k = String(r.createTime || '').slice(0, 10)
    if (!k) return
    if (r.sendStatus === 'sent') okMap[k] = (okMap[k] || 0) + 1
    else if (r.sendStatus === 'failed') failMap[k] = (failMap[k] || 0) + 1
  })
  const okData = days.map(d => okMap[d.key] || 0)
  const failData = days.map(d => failMap[d.key] || 0)
  chartSum.ok = okData.reduce((a, b) => a + b, 0)
  chartSum.fail = failData.reduce((a, b) => a + b, 0)

  if (!pushChart) pushChart = echarts.init(pushChartRef.value)
  pushChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['成功', '失败'], right: 0, top: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 12 } },
    grid: { left: 8, right: 8, top: 34, bottom: 4, containLabel: true },
    xAxis: { type: 'category', data: days.map(d => d.label), axisTick: { show: false }, axisLine: { lineStyle: { color: '#e4e7ed' } }, axisLabel: { color: '#909399', fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#f0f2f5' } }, axisLabel: { color: '#909399', fontSize: 11 } },
    series: [
      { name: '成功', type: 'bar', stack: 'x', barMaxWidth: 26, itemStyle: { color: '#43c59e', borderRadius: [0, 0, 0, 0] }, data: okData },
      { name: '失败', type: 'bar', stack: 'x', barMaxWidth: 26, itemStyle: { color: '#f56c6c', borderRadius: [3, 3, 0, 0] }, data: failData }
    ]
  })
}

function renderSubChart(rows) {
  if (!subChartRef.value) return
  const days = lastDays(7)
  const addMap = {}
  rows.forEach(r => {
    const k = String(r.createTime || '').slice(0, 10)
    if (k) addMap[k] = (addMap[k] || 0) + 1
  })
  // 累计：用总数减去"今天之后新增的"，倒推每天末的累计值
  const todayTotal = rows.length
  const addList = days.map(d => addMap[d.key] || 0)
  const cum = []
  let acc = todayTotal - addList.reduce((a, b) => a + b, 0)
  addList.forEach(n => { acc += n; cum.push(acc) })

  if (!subChart) subChart = echarts.init(subChartRef.value)
  subChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 8, right: 12, top: 30, bottom: 4, containLabel: true },
    xAxis: { type: 'category', data: days.map(d => d.label), boundaryGap: false, axisTick: { show: false }, axisLine: { lineStyle: { color: '#e4e7ed' } }, axisLabel: { color: '#909399', fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1, splitLine: { lineStyle: { color: '#f0f2f5' } }, axisLabel: { color: '#909399', fontSize: 11 } },
    series: [{
      name: '订阅人数',
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: cum,
      itemStyle: { color: '#8b7cf6' },
      lineStyle: { width: 2.5 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(139,124,246,.28)' },
          { offset: 1, color: 'rgba(139,124,246,.02)' }
        ])
      }
    }]
  })
}

let loadingAll = false

async function loadAll() {
  if (loadingAll) return
  loadingAll = true
  try { await loadAllInner() } finally { loadingAll = false }
}

async function loadAllInner() {
  loading.act = true
  try {
    const r = await listActivity({ pageNum: 1, pageSize: 10, actState: 'open' })
    activities.value = r.rows || []
    cards.value[0].value = r.total ?? 0
  } catch (e) { } finally { loading.act = false }

  try {
    const r = await listActivity({ pageNum: 1, pageSize: 1 })
    cards.value[1].value = r.total ?? 0
  } catch (e) { }

  // 订阅者：拿全量用于增长曲线
  try {
    const r = await listSubscriber({ pageNum: 1, pageSize: 500, status: '0' })
    cards.value[2].value = r.total ?? 0
    await nextTick()
    renderSubChart(r.rows || [])
  } catch (e) { }

  loading.del = true
  try {
    const r = await listDelivery({ pageNum: 1, pageSize: 1000 })
    deliveries.value = (r.rows || []).slice(0, 10)
    await nextTick()
    renderPushChart(r.rows || [])
  } catch (e) { } finally { loading.del = false }

  try {
    const r = await listDelivery({ pageNum: 1, pageSize: 1, sendStatus: 'sent' })
    cards.value[3].value = r.total ?? 0
  } catch (e) { }

  const d = new Date()
  const p2 = n => String(n).padStart(2, '0')
  lastUpdate.value = `${p2(d.getHours())}:${p2(d.getMinutes())}:${p2(d.getSeconds())}`
}

function onResize() {
  pushChart && pushChart.resize()
  subChart && subChart.resize()
}


// 讲座（jwxt 教务）统计：只取数量，不拉列表
function loadLectureStat() {
  request({ url: '/system/lecture/status', method: 'get' })
    .then(res => {
      const d = (res && res.data) ? res.data : (res || {})
      const st = d.stat || {}
      cards.value[4].value = st.total != null ? st.total : '-'
      cards.value[5].value = st.canJoinCnt != null ? st.canJoinCnt : '-'
    })
    .catch(() => {})
}

onMounted(() => {
  loadLectureStat()
  loadAll()
  window.addEventListener('resize', onResize)
  // 每分钟自动刷新；页面在后台标签页时跳过，省请求
  refreshTimer = setInterval(() => {
    if (!document.hidden) loadAll()
  }, REFRESH_MS)
})

onBeforeUnmount(() => {
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  window.removeEventListener('resize', onResize)
  pushChart && pushChart.dispose()
  subChart && subChart.dispose()
})
</script>

<style scoped lang="scss">
.dashboard { padding: 4px; }
.refresh-bar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px; padding: 0 2px;
}
.refresh-hint { font-size: 12px; color: #909399; }
.stat-row { margin-bottom: 0; }
.stat-card {
  border-radius: 10px;
  padding: 18px 20px;
  color: #fff;
  margin-bottom: 16px;
  &.blue   { background: linear-gradient(135deg, #4b8bf5, #2f6fdc); }
  &.green  { background: linear-gradient(135deg, #43c59e, #2ba57f); }
  &.purple { background: linear-gradient(135deg, #8b7cf6, #6c5ce7); }
  &.orange { background: linear-gradient(135deg, #f5a623, #e8890c); }
}
.stat-value { font-size: 30px; font-weight: 600; line-height: 1.15; font-variant-numeric: tabular-nums; }
.stat-label { font-size: 13px; opacity: .88; margin-top: 4px; }

.chart-row { margin-bottom: 0; }
.chart { height: 210px; width: 100%; }

.panel {
  border-radius: 10px;
  margin-bottom: 16px;
  :deep(.el-card__header) { padding: 12px 16px; }
  :deep(.el-card__body) { padding: 10px 16px 16px; }
}
.panel-head { display: flex; align-items: center; justify-content: space-between; }
.panel-title { font-size: 15px; font-weight: 600; }
.panel-sub { font-size: 12px; color: #909399; }

.tip { :deep(.el-card__body) { padding: 18px 20px; } }
.tip-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; }
.tip-k { font-size: 12px; color: #909399; margin-bottom: 2px; }
.tip-v { font-size: 14px; color: #303133; a { color: #409eff; text-decoration: none; } }
</style>
