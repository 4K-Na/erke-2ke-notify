<template>
  <div class="app-container ops-page">
    <!-- 服务状态 -->
    <el-card shadow="never" class="panel">
      <template #header>
        <div class="panel-head">
          <span class="panel-title">服务状态</span>
          <div class="head-actions">
            <span class="hint">点服务名展开日志 · 最新在上</span>
            <el-button size="small" :loading="loading" @click="loadServices">刷新</el-button>
          </div>
        </div>
      </template>

      <div v-loading="loading && !services.length" class="svc-list">
        <!-- 2ke 登录凭据（默认折叠） -->
        <div class="svc-block ck-block">
          <div class="svc-row ck-row" :class="{ open: ckExpanded }" @click="ckExpanded = !ckExpanded">
            <span class="dot" :class="ckDot"></span>
            <span class="svc-name">2ke 登录凭据</span>
            <span class="svc-state" :class="ckDot === 'ok' ? 'ok' : (ckDot === 'bad' ? 'bad' : 'wait')">
              {{ cookie.healthy ? '正常' : '异常' }}
            </span>
            <span class="svc-uptime">
              <template v-if="cookie.tokenDaysLeft !== undefined">剩 {{ cookie.tokenDaysLeft }} 天</template>
              <template v-else>—</template>
            </span>
            <span class="svc-unit">cookie</span>
            <span class="svc-arrow" :class="{ rotated: ckExpanded }">▸</span>
            <el-button size="small" type="primary" plain class="svc-btn"
                       @click.stop="openCookieDialog">更新</el-button>
          </div>

          <div v-if="ckExpanded" class="ck-detail" @click.stop>
            <div v-loading="ckLoading" class="ck-grid">
              <div class="ck-item">
                <div class="ck-k">凭据到期</div>
                <div class="ck-v" :class="{ warn: (cookie.tokenDaysLeft ?? 999) <= 30 }">
                  {{ cookie.tokenExpireAt || '—' }}
                  <span v-if="cookie.tokenDaysLeft !== undefined" class="ck-sub">（剩 {{ cookie.tokenDaysLeft }} 天）</span>
                </div>
              </div>
              <div class="ck-item">
                <div class="ck-k">会话窗口</div>
                <div class="ck-v">
                  {{ cookie.sessionExpireAt || '—' }}
                  <span class="ck-sub">（自动续期）</span>
                </div>
              </div>
              <div class="ck-item">
                <div class="ck-k">保存于</div>
                <div class="ck-v">{{ cookie.savedAt || '—' }}</div>
              </div>
              <div class="ck-item">
                <div class="ck-k">会话用户</div>
                <div class="ck-v">{{ cookie.sessionUser || '—' }}</div>
              </div>
              <div class="ck-item">
                <div class="ck-k">Cookie 数量</div>
                <div class="ck-v">{{ cookie.cookieCount ?? '—' }}</div>
              </div>
              <div class="ck-item">
                <div class="ck-k">采集器</div>
                <div class="ck-v" :class="cookie.collectorActive === 'active' ? 'ok' : 'warn'">
                  {{ cookie.collectorActive || '—' }}
                </div>
              </div>
            </div>
            <div class="ck-note">{{ cookie.message || '' }}</div>
          </div>
        </div>

        <div v-for="s in services" :key="s.key" class="svc-block">
          <!-- 服务行 -->
          <div class="svc-row" :class="{ open: expanded === s.key }" @click="toggle(s.key)">
            <span class="dot" :class="dotClass(s.active)"></span>
            <span class="svc-name">{{ s.name }}</span>
            <span class="svc-state" :class="dotClass(s.active)">{{ stateText(s.active) }}</span>
            <span class="svc-uptime">{{ s.uptime }}</span>
            <span class="svc-unit">{{ s.unit }}</span>
            <span class="svc-arrow" :class="{ rotated: expanded === s.key }">▸</span>
            <el-button
              size="small"
              type="primary"
              plain
              class="svc-btn"
              :loading="restarting === s.key"
              @click.stop="doRestart(s)">
              {{ s.action === 'reload' ? '重载' : '重启' }}
            </el-button>
          </div>

          <!-- 展开的日志 -->
          <div v-if="expanded === s.key" class="log-panel" @click.stop>
            <div class="log-toolbar">
              <el-radio-group v-model="level" size="small" @change="loadLogs">
                <el-radio-button value="ALL">全部</el-radio-button>
                <el-radio-button value="ERROR">
                  错误<span v-if="logStat.errorCount" class="cnt err">{{ logStat.errorCount }}</span>
                </el-radio-button>
                <el-radio-button value="WARN">
                  警告<span v-if="logStat.warnCount" class="cnt warn">{{ logStat.warnCount }}</span>
                </el-radio-button>
                <el-radio-button value="INFO">信息</el-radio-button>
              </el-radio-group>
              <div class="log-right">
                <el-select v-model="since" size="small" style="width: 112px" @change="loadLogs">
                  <el-option value="1h" label="最近 1 小时" />
                  <el-option value="6h" label="最近 6 小时" />
                  <el-option value="24h" label="最近 24 小时" />
                  <el-option value="all" label="全部" />
                </el-select>
                <el-select v-model="lines" size="small" style="width: 92px" @change="loadLogs">
                  <el-option :value="100" label="100 行" />
                  <el-option :value="200" label="200 行" />
                  <el-option :value="500" label="500 行" />
                  <el-option :value="1000" label="1000 行" />
                </el-select>
                <el-button size="small" :loading="logLoading" @click="loadLogs">刷新</el-button>
              </div>
            </div>

            <div v-loading="logLoading" class="log-body">
              <div v-if="!logs.length && !logLoading" class="log-empty">
                <div class="empty-title">这段时间没有日志</div>
                <div class="empty-sub">
                  {{ sinceLabel }}内该服务没有输出。
                  <template v-if="expanded === 'wecom'">回调服务只在企业微信发请求时才写日志，平时静默是正常的。</template>
                  <template v-else-if="expanded === 'nginx' || expanded === 'mysql' || expanded === 'redis'">这个服务只在有访问或错误时才输出。</template>
                </div>
                <div class="empty-actions">
                  <el-button v-if="since !== '24h'" size="small" @click="switchSince('24h')">看最近 24 小时</el-button>
                  <el-button v-if="since !== 'all'" size="small" @click="switchSince('all')">看全部</el-button>
                </div>
              </div>
              <div v-for="(l, i) in logs" :key="i" class="log-line">
                <span class="log-ts">{{ fmtTs(l.ts) }}</span>
                <span class="log-lv" :class="'lv-' + l.level">{{ l.level }}</span>
                <span class="log-msg">{{ l.msg }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 开机自启 -->
    <el-card shadow="never" class="panel">
      <template #header>
        <div class="panel-head">
          <span class="panel-title">关机重启说明</span>
          <el-link type="primary" :underline="false" @click="showBoot = !showBoot">
            {{ showBoot ? '收起' : '展开' }}
          </el-link>
        </div>
      </template>
      <div v-if="showBoot" class="boot-info">
        <p class="boot-line">
          <b>所有服务都是 enabled，服务器关机重启后会自动按依赖顺序拉起，不需要手动操作。</b>
        </p>
        <div class="boot-grid">
          <div class="boot-item">
            <div class="boot-k">启动顺序</div>
            <div class="boot-v">
              MySQL + Redis → 若依后端<br>
              MySQL → 采集器 / 推送器<br>
              回调服务、Nginx 独立
            </div>
          </div>
          <div class="boot-item">
            <div class="boot-k">自启状态</div>
            <div class="boot-v">
              <span v-for="s in services" :key="s.key" class="boot-tag" :class="s.enabled === 'enabled' ? 'ok' : 'bad'">
                {{ s.name }}
              </span>
            </div>
          </div>
          <div class="boot-item">
            <div class="boot-k">开机后怎么确认</div>
            <div class="boot-v">
              打开本页，七个服务全绿即正常。<br>
              如果某个是灰的，点它的「重启」。
            </div>
          </div>
          <div class="boot-item">
            <div class="boot-k">手动执行（SSH）</div>
            <div class="boot-v mono">systemctl restart ruoyi-mysql ruoyi-redis<br>systemctl restart ruoyi-app nginx 2ke-wecom<br>systemctl restart 2ke-hub-mysql 2ke-dispatcher</div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
  <!-- 更新 Cookie 弹框 -->
  <el-dialog v-model="ckDialog" title="更新第二课堂登录凭据" :width="'min(760px, 94vw)'" top="6vh" destroy-on-close>
    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
      <template #title>
        从浏览器复制整行 Cookie，必须包含 <code>__access_token</code>
      </template>
      <div class="ck-help">
        1. Chrome 打开 <b>https://2ke.jmu.edu.cn</b> 并确认已登录<br>
        2. F12 → <b>Network</b> → 随便点一个 2ke 的请求<br>
        3. 右侧 <b>Request Headers</b> → 找到 <code>Cookie</code> → 右键「Copy value」<br>
        4. 粘贴到下面
      </div>
    </el-alert>

    <el-input
      v-model="ckInput"
      type="textarea"
      :rows="8"
      placeholder="__access_token=eyJ...; __Host-authjs.csrf-token=...; __Secure-authjs.session-token=..."
      style="font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 12px"
    />

    <div class="ck-input-meta">
      <span :class="{ warn: ckInput && !ckInput.includes('__access_token') }">
        {{ ckInput ? ckInput.length + ' 字符' : '未输入' }}
        <span v-if="ckInput && !ckInput.includes('__access_token')"> · 缺少 __access_token</span>
      </span>
    </div>

    <div v-if="ckResult" class="ck-result" :class="ckResult.ok ? 'ok' : 'bad'">
      <div class="ck-result-title">{{ ckResult.ok ? '✓ 更新成功' : '✗ 更新失败' }}</div>
      <div class="ck-result-msg">{{ ckResult.msg }}</div>
      <pre v-if="ckResult.log" class="ck-result-log">{{ ckResult.log }}</pre>
    </div>

    <template #footer>
      <el-button @click="ckDialog = false">取消</el-button>
      <el-button type="primary" :loading="ckSaving" :disabled="!ckInput.trim()" @click="doUpdateCookie">
        验证并更新
      </el-button>
    </template>
  </el-dialog>

</template>

<script setup name="Ops">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import request from '@/utils/request'

const { proxy } = getCurrentInstance()

const services = ref([])
const loading = ref(false)
const expanded = ref('')
const logs = ref([])
const logLoading = ref(false)
const logStat = reactive({ errorCount: 0, warnCount: 0 })
const level = ref('ALL')
const lines = ref(200)
const since = ref('1h')
const restarting = ref('')
const showBoot = ref(true)

// ── Cookie ──
const cookie = ref({})
const ckLoading = ref(false)
const ckExpanded = ref(false)
const ckDialog = ref(false)
const ckInput = ref('')
const ckSaving = ref(false)
const ckResult = ref(null)
let timer = null
let ckTimer = null

function stateText(a) {
  return { active: '运行中', inactive: '已停止', failed: '失败', activating: '启动中', deactivating: '停止中' }[a] || a || '未知'
}
function dotClass(a) {
  return { active: 'ok', inactive: 'off', failed: 'bad', activating: 'wait', deactivating: 'wait' }[a] || 'off'
}
function fmtTs(ts) {
  if (!ts) return ''
  // 2026-10-21T22:08:34+08:00 -> 22:08:34
  const m = String(ts).match(/T(\d{2}:\d{2}:\d{2})/)
  return m ? m[1] : ts.slice(-14, -6)
}

const ckDot = computed(() => {
  if (!cookie.value.exists) return 'off'
  if (cookie.value.healthy === false) return 'bad'
  const d = cookie.value.tokenDaysLeft
  if (typeof d === 'number' && d <= 30) return 'wait'
  return 'ok'
})

function loadCookie() {
  ckLoading.value = true
  request({ url: '/system/ops/cookie/status', method: 'get' })
    .then(res => {
      const d = (res && res.data) ? res.data : res
      cookie.value = d || {}
    })
    .catch(() => { cookie.value = { exists: false, message: '查询失败' } })
    .finally(() => { ckLoading.value = false })
}

function openCookieDialog() {
  ckInput.value = ''
  ckResult.value = null
  ckDialog.value = true
}

function doUpdateCookie() {
  const v = (ckInput.value || '').trim()
  if (!v) return
  if (!v.includes('__access_token')) {
    proxy.$modal.msgWarning('内容里没有 __access_token，2ke 认证依赖它，请完整复制整行 Cookie')
    return
  }
  ckSaving.value = true
  ckResult.value = null
  request({
    url: '/system/ops/cookie/update',
    method: 'post',
    data: { cookie: v },
    timeout: 90000
  }).then(res => {
    ckResult.value = {
      ok: true,
      msg: (res && res.msg) || '更新成功',
      log: (res && res.data && res.data.recentLog) || ''
    }
    proxy.$modal.msgSuccess((res && res.msg) || '更新成功')
    loadCookie()
  }).catch(err => {
    const r = err && err.response && err.response.data
    ckResult.value = {
      ok: false,
      msg: (r && r.msg) || (err && err.message) || '更新失败',
      log: (r && r.data && r.data.recentLog) || ''
    }
  }).finally(() => { ckSaving.value = false })
}

function loadServices() {
  loading.value = true
  request({ url: '/system/ops/services', method: 'get' })
    .then(res => {
      const d = (res && res.data) ? res.data : res
      services.value = Array.isArray(d) ? d : []
    })
    .catch(() => {})
    .finally(() => { loading.value = false })
}

function loadLogs() {
  if (!expanded.value) return
  logLoading.value = true
  request({
    url: '/system/ops/logs',
    method: 'get',
    params: { key: expanded.value, lines: lines.value, level: level.value, since: since.value }
  }).then(res => {
    const d = (res && res.data) ? res.data : res
    logs.value = d.rows || []
    logStat.errorCount = d.errorCount || 0
    logStat.warnCount = d.warnCount || 0
  }).catch(() => { logs.value = [] })
    .finally(() => { logLoading.value = false })
}

const sinceLabel = computed(() => ({
  '1h': '最近 1 小时',
  '6h': '最近 6 小时',
  '24h': '最近 24 小时',
  'all': '全部时间'
}[since.value] || '当前时间段'))

function switchSince(v) {
  since.value = v
  loadLogs()
}

function toggle(key) {
  if (expanded.value === key) {
    expanded.value = ''
    logs.value = []
    return
  }
  expanded.value = key
  level.value = 'ALL'
  since.value = '1h'
  loadLogs()
}

function doRestart(s) {
  const word = s.action === 'reload' ? '重载' : '重启'
  proxy.$modal.confirm(`确认${word}「${s.name}」？`).then(() => {
    restarting.value = s.key
    return request({ url: '/system/ops/restart', method: 'post', params: { key: s.key } })
  }).then(res => {
    proxy.$modal.msgSuccess((res && res.msg) || `${s.name} 已${word}`)
    if (s.key === 'backend') {
      proxy.$modal.msgWarning('后端约 15 秒后恢复，页面将自动刷新')
      setTimeout(() => { window.location.reload() }, 16000)
      return
    }
    setTimeout(loadServices, 1200)
    if (expanded.value === s.key) setTimeout(loadLogs, 1500)
  }).catch(() => {}).finally(() => { restarting.value = '' })
}

onMounted(() => {
  loadServices()
  loadCookie()
  // 每 30 秒刷新一次状态；展开的日志不自动拉，避免刷屏
  timer = setInterval(() => { if (!document.hidden) loadServices() }, 30000)
  // Cookie 状态单独低频刷新，不必每 30 秒都请求 2ke
  ckTimer = setInterval(() => { if (!document.hidden) loadCookie() }, 300000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  if (ckTimer) clearInterval(ckTimer)
})
</script>

<style scoped>
.ops-page { padding: 4px; }
.panel {
  border-radius: 10px;
  margin-bottom: 16px;
  :deep(.el-card__header) { padding: 12px 16px; }
  :deep(.el-card__body) { padding: 8px 16px 16px; }
}
.panel-head { display: flex; align-items: center; justify-content: space-between; }
.panel-title { font-size: 15px; font-weight: 600; }

/* Cookie 卡片 */
/* Cookie 折叠区 */
.ck-detail {
  margin: 0 6px 14px 28px;
  border: 1px solid #eef0f3;
  border-radius: 8px;
  background: #fbfcfd;
  padding: 12px 14px;
}
.ck-note { margin-top: 8px; font-size: 12px; color: #a8abb2; }
.ck-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px 18px;
}
.ck-item { background: #f7f8fa; border-radius: 7px; padding: 9px 12px; }
.ck-k { font-size: 11.5px; color: #909399; margin-bottom: 4px; }
.ck-v { font-size: 13px; color: #303133; }
.ck-v.ok { color: #2ba57f; }
.ck-v.warn { color: #e6a23c; }
.ck-sub { font-size: 11.5px; color: #b0b5bd; }

/* 更新弹框 */
.ck-help { font-size: 12.5px; line-height: 1.9; color: #606266; margin-top: 4px; }
.ck-help code, .el-alert__title code {
  background: #eef1f5; padding: 1px 5px; border-radius: 3px;
  font-size: 12px; color: #1a6dff;
}
.ck-input-meta { margin-top: 6px; font-size: 12px; color: #b0b5bd; }
.ck-input-meta .warn { color: #e6a23c; }
.ck-result { margin-top: 12px; border-radius: 8px; padding: 12px 14px; }
.ck-result.ok { background: #eaf8f3; border: 1px solid #b8e6d5; }
.ck-result.bad { background: #fef0f0; border: 1px solid #fbc9c9; }
.ck-result-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.ck-result.ok .ck-result-title { color: #2ba57f; }
.ck-result.bad .ck-result-title { color: #f56c6c; }
.ck-result-msg { font-size: 12.5px; color: #505560; line-height: 1.7; }
.ck-result-log {
  margin: 8px 0 0; padding: 8px 10px; background: rgba(0,0,0,.04);
  border-radius: 5px; font-size: 11.5px; color: #606266;
  max-height: 130px; overflow: auto; white-space: pre-wrap;
}
.head-actions { display: flex; align-items: center; gap: 10px; }
.hint { font-size: 12px; color: #a8abb2; }

/* 服务行 */
.svc-block { border-bottom: 1px solid #f2f3f5; }
.svc-block:last-child { border-bottom: none; }
.svc-row {
  display: grid;
  grid-template-columns: 12px 1fr 76px 92px 1fr 18px 68px;
  align-items: center;
  gap: 10px;
  padding: 11px 6px;
  cursor: pointer;
  border-radius: 6px;
  transition: background .12s;
}
.svc-row:hover { background: #f7f8fa; }
.svc-row.open { background: #f2f6ff; }
.dot { width: 8px; height: 8px; border-radius: 50%; }
.dot.ok { background: #43c59e; box-shadow: 0 0 0 3px rgba(67,197,158,.18); }
.dot.off { background: #c8cbd1; }
.dot.bad { background: #f56c6c; box-shadow: 0 0 0 3px rgba(245,108,108,.18); }
.dot.wait { background: #e6a23c; }
.svc-name { font-size: 14px; font-weight: 500; }
.svc-state { font-size: 13px; }
.svc-state.ok { color: #2ba57f; }
.svc-state.off { color: #909399; }
.svc-state.bad { color: #f56c6c; }
.svc-state.wait { color: #e6a23c; }
.svc-uptime { font-size: 12px; color: #909399; }
.svc-unit { font-size: 12px; color: #c0c4cc; font-family: ui-monospace, Menlo, Consolas, monospace; }
.svc-arrow { color: #c0c4cc; transition: transform .15s; }
.svc-arrow.rotated { transform: rotate(90deg); color: #409eff; }
.svc-btn { justify-self: end; }

/* 手机端：服务行改弹性换行，避免服务名被固定列挤成竖排（375px 屏曾只剩约 9px） */
@media (max-width: 768px) {
  .svc-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 8px;
    padding: 10px 4px;
  }
  .svc-name { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .svc-state { font-size: 12px; }
  .svc-uptime { font-size: 12px; }
  .svc-unit { font-size: 12px; }
  .svc-btn { margin-left: auto; }
  .log-panel { margin-left: 4px; margin-right: 4px; }
  .ck-grid { grid-template-columns: 1fr; }
}

/* 日志面板 */
.log-panel {
  margin: 0 6px 14px 28px;
  border: 1px solid #eef0f3;
  border-radius: 8px;
  background: #fbfcfd;
  overflow: hidden;
}
.log-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: #f7f8fa; border-bottom: 1px solid #eef0f3;
}
.log-right { display: flex; align-items: center; gap: 8px; }
.cnt { margin-left: 3px; padding: 0 4px; border-radius: 8px; font-size: 11px; color: #fff; }
.cnt.err { background: #f56c6c; }
.cnt.warn { background: #e6a23c; }

.log-body { max-height: 420px; overflow-y: auto; padding: 6px 0; }
.log-empty { padding: 30px 20px; text-align: center; }
.empty-title { font-size: 13.5px; color: #909399; margin-bottom: 6px; }
.empty-sub { font-size: 12px; color: #b0b5bd; line-height: 1.8; max-width: 520px; margin: 0 auto 14px; }
.empty-actions { display: flex; gap: 8px; justify-content: center; }
.log-line {
  display: grid;
  grid-template-columns: 68px 52px 1fr;
  gap: 8px;
  padding: 3px 12px;
  font-family: ui-monospace, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.65;
}
.log-line:hover { background: #f5f7fa; }
.log-ts { color: #a8abb2; }
.log-lv { font-weight: 600; }
.lv-INFO { color: #7a8290; }
.lv-WARN { color: #e6a23c; }
.lv-ERROR { color: #f56c6c; }
.log-msg { color: #303133; word-break: break-all; white-space: pre-wrap; }

/* 开机说明 */
.boot-line { font-size: 13px; color: #303133; margin-bottom: 14px; }
.boot-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
.boot-item { background: #f7f8fa; border-radius: 8px; padding: 12px 14px; }
.boot-k { font-size: 12px; color: #909399; margin-bottom: 6px; }
.boot-v { font-size: 13px; color: #303133; line-height: 1.8; }
.boot-v.mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11.5px; color: #606266; }
.boot-tag { display: inline-block; margin: 0 4px 4px 0; padding: 1px 7px; border-radius: 9px; font-size: 11.5px; }
.boot-tag.ok { background: #e8f8f2; color: #2ba57f; }
.boot-tag.bad { background: #fef0f0; color: #f56c6c; }
</style>
