<template>
  <div class="app-container qr-page">
    <el-alert type="info" :closable="false" show-icon class="tip">
      <template #title>
        订阅页两个码的来源不同：左码是一次性邀请链接（<b>永久有效</b>）；右码在企业微信侧
        <b>7 天过期</b>，且企业微信没有开放接口能自动生成，只能从 App 里「重新获取」后把截图传上来。
      </template>
    </el-alert>

    <el-row :gutter="14">
      <!-- 左码 -->
      <el-col :xs="24" :sm="12">
        <el-card shadow="never" class="qr-card">
          <div class="hd"><span class="no">①</span>加入企业微信<span class="badge">永久</span></div>
          <div class="img-box">
            <img :src="joinUrl" alt="加入企业微信" />
          </div>
          <div class="meta">不需要更换 · 内容为长期邀请链接</div>
        </el-card>
      </el-col>

      <!-- 右码 -->
      <el-col :xs="24" :sm="12">
        <el-card shadow="never" class="qr-card">
          <div class="hd">
            <span class="no">②</span>关注微信插件
            <span class="badge" :class="badgeClass">{{ expiryText }}</span>
          </div>
          <div class="img-box">
            <img :src="pluginUrl" alt="关注微信插件" />
          </div>
          <div class="meta">
            <span v-if="status.pluginTime">当前码更新于 {{ status.pluginTime }}</span>
            <span v-else>还没有码</span>
            <span v-if="status.daysLeft !== null && status.daysLeft !== undefined" class="ml8">
              · 剩 {{ status.daysLeft }} 天
            </span>
          </div>

          <div class="actions">
            <input ref="fileRef" type="file" accept="image/*" style="display:none" @change="onFile" />
            <el-button type="primary" :loading="uploading" :disabled="!status.uploadReady" @click="pick">
              上传新码
            </el-button>
            <el-button :loading="loading" @click="load">刷新</el-button>
          </div>

          <div class="howto">
            <div>换码步骤：企业微信 → <b>我</b> → <b>设置</b> → <b>微信插件</b> → 点「重新获取」→ 截图 → 回到这里上传</div>
            <div class="dim">上传后自动：解码校验 → 裁成 600×600 → 覆盖上线 → 更新到期日。不是企业微信的码会被拒绝。</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 提醒说明 -->
    <el-card shadow="never" class="qr-card note-card">
      <div class="note-title">临期提醒</div>
      <div class="note-body">
        到期前 <b>2 天</b>会自动给你发一条企业微信（收件人 <code>{{ adminUserId }}</code>，每天最多一条），
        里面带这个页面的入口。已订阅的同学不受码过期影响，只有新同学需要有效码。
      </div>
    </el-card>
  </div>
</template>

<script setup name="Qrcode">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const uploading = ref(false)
const status = ref({})
const fileRef = ref(null)
const adminUserId = ref('LvZhiYi')

const pluginUrl = computed(() => `https://example.com/plugin.png?v=${status.value.pluginVersion || 0}`)
const joinUrl = computed(() => `https://example.com/join.png?v=${status.value.joinVersion || 0}`)

const expiryText = computed(() => {
  const d = status.value.daysLeft
  if (d === null || d === undefined) return '未记录到期'
  if (d < 0) return '已过期'
  if (d === 0) return '今天到期'
  return `剩 ${d} 天`
})

const badgeClass = computed(() => {
  const d = status.value.daysLeft
  if (d === null || d === undefined || d < 0) return 'bad'
  if (d <= 2) return 'warn'
  return 'ok'
})

function load() {
  loading.value = true
  request({ url: '/system/qrcode/status', method: 'get' })
    .then(res => {
      const d = (res && res.data) ? res.data : res
      status.value = d || {}
    })
    .catch(() => {})
    .finally(() => { loading.value = false })
}

function pick() {
  if (!status.value.uploadReady) {
    ElMessage.warning('本机图像服务未就绪，请联系运维检查 qr-upload.service')
    return
  }
  fileRef.value && fileRef.value.click()
}

function onFile(e) {
  const f = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!f) return
  if (f.size > 12 * 1024 * 1024) {
    ElMessage.error('图片超过 12MB，请重新截图')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    const data = String(reader.result || '')
    ElMessageBox.confirm(
      '确认用这张截图替换订阅页的「关注微信插件」二维码？',
      '更换右码',
      { confirmButtonText: '确认替换', cancelButtonText: '取消', type: 'warning' }
    ).then(() => doUpload(data)).catch(() => {})
  }
  reader.readAsDataURL(f)
}

function doUpload(data) {
  uploading.value = true
  request({
    url: '/system/qrcode/upload',
    method: 'post',
    headers: { 'Content-Type': 'application/json' },
    data: { data: data }
  })
    .then(res => {
      const d = (res && res.data) ? res.data : res
      let msg = '已更新'
      try {
        const j = typeof d === 'string' ? JSON.parse(d) : d
        if (j && j.expiry) msg = `已更新，有效期至 ${j.expiry}`
      } catch (err) {}
      ElMessage.success(msg)
      load()
    })
    .catch(err => {
      const m = (err && (err.msg || err.message)) || ''
      ElMessage.error(m ? ('更新失败：' + m) : '更新失败，请检查截图是否是企业微信的插件码')
    })
    .finally(() => { uploading.value = false })
}

onMounted(load)
</script>

<style scoped>
.qr-page { max-width: 1080px; }
.tip { margin-bottom: 14px; }
.qr-card { margin-bottom: 14px; }
.hd {
  display: flex; align-items: center; gap: 6px;
  font-size: 15px; font-weight: 600; margin-bottom: 12px;
}
.hd .no { color: #909399; font-weight: 400; }
.badge {
  margin-left: auto; font-size: 12px; font-weight: 400;
  padding: 1px 8px; border-radius: 10px;
}
.badge.ok { background: #f0f9eb; color: #529b2e; }
.badge.warn { background: #fdf6ec; color: #b88230; }
.badge.bad { background: #fef0f0; color: #c45656; }
.img-box {
  background: #fafafa; border: 1px solid #ebeef5; border-radius: 10px;
  padding: 14px; display: flex; justify-content: center;
}
.img-box img { width: 100%; max-width: 260px; display: block; border-radius: 6px; }
.meta { margin-top: 10px; font-size: 12px; color: #909399; }
.ml8 { margin-left: 8px; }
.actions { margin-top: 12px; display: flex; gap: 10px; flex-wrap: wrap; }
.howto {
  margin-top: 14px; padding-top: 12px; border-top: 1px dashed #ebeef5;
  font-size: 12.5px; color: #606266; line-height: 1.9;
}
.howto .dim { color: #a8abb2; }
.note-card .note-title { font-size: 14px; font-weight: 600; margin-bottom: 8px; }
.note-card .note-body { font-size: 13px; color: #606266; line-height: 1.9; }
.note-card code { background: #f5f7fa; padding: 1px 6px; border-radius: 4px; }
@media (max-width: 768px) {
  .qr-page { padding: 10px; }
  .img-box img { max-width: 200px; }
  .actions :deep(.el-button) { flex: 1 1 auto; }
}
</style>
