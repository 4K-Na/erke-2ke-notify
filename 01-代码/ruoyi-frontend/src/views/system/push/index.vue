<template>
  <div class="app-container push-page">
    <el-row :gutter="16" justify="center">
      <!-- 发送表单 -->
      <el-col :xs="24" :sm="24" :md="18" :lg="14">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <span class="panel-title">发送自定义消息</span>
              <span class="panel-sub">临时通知 / 故障提醒，不依赖 2ke 是否有新活动</span>
            </div>
          </template>

          <el-form :model="form" label-width="86px">
            <el-form-item label="发给谁">
              <el-radio-group v-model="form.scope">
                <el-radio-button value="self">只发给我</el-radio-button>
                <el-radio-button value="all">发给全体</el-radio-button>
                <el-radio-button value="ids">指定订阅者</el-radio-button>
              </el-radio-group>
              <div class="hint" v-if="form.scope === 'self'">
                发给管理员（{{ targets.adminUserid || '未配置' }}），适合自己测试
              </div>
              <div class="hint" v-else-if="form.scope === 'all'">
                发给应用可见范围内的所有成员，目前 {{ targets.subscribers.length }} 人订阅
              </div>
            </el-form-item>

            <el-form-item v-if="form.scope === 'ids'" label="接收人">
              <el-select v-model="form.userIds" multiple filterable placeholder="选择订阅者" style="width: 100%">
                <el-option
                  v-for="s in targets.subscribers"
                  :key="s.externalId"
                  :label="`${s.name || s.externalId}${s.className ? ' · ' + s.className : ''}`"
                  :value="s.externalId" />
              </el-select>
            </el-form-item>

            <el-form-item label="标题">
              <el-input v-model="form.title" placeholder="可选，会显示为【标题】" maxlength="40" show-word-limit />
            </el-form-item>

            <el-form-item label="正文">
              <el-input
                v-model="form.content"
                type="textarea"
                :rows="8"
                placeholder="例如：今晚 23:00 服务器维护，推送可能延迟，明早恢复。" />
              <div class="hint">
                {{ byteLen }} / 2048 字节（企业微信硬上限，中文约 680 字）
                <span v-if="byteLen > 2048" class="warn">已超出上限，无法发送</span>
                <span v-else-if="byteLen > 1800" class="warn">接近上限</span>
              </div>
              <pre v-if="previewText" style="margin-top:10px;padding:10px 12px;background:#f7f8fa;border:1px solid #ebeef5;border-radius:6px;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-word;font-family:inherit">{{ previewText }}</pre>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="sending" :disabled="byteLen > 2048 || (form.scope === 'ids' && !form.userIds.length)" @click="handleSend">发 送</el-button>
              <el-button :loading="imgUploading" @click="pickImage">插入图片</el-button>
              <el-button @click="handleReset">清 空</el-button>
              <input ref="imgRef" type="file" accept="image/png,image/jpeg,image/gif,image/webp" style="display:none" @change="onImage" />
            </el-form-item>
            <div class="img-tip">
              企业微信一条消息只能是一种类型：勾了图片就<b>分两条发</b>——先发文字，紧接着发图片。
              不收图片就只发文字。
            </div>
            <div v-if="imgPreview" class="img-preview">
              <img :src="imgPreview" alt="待发送图片" />
              <div class="img-meta">
                <span>{{ imgMeta }}</span>
                <el-button link type="danger" @click="clearImage">移除</el-button>
              </div>
            </div>
          </el-form>
        </el-card>
        <el-card shadow="never" class="panel" v-if="lastResult">
          <template #header>
            <div class="panel-head"><span class="panel-title">上次发送结果</span></div>
          </template>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="状态">
              <el-tag :type="lastResult.ok ? 'success' : 'danger'" size="small">
                {{ lastResult.ok ? '成功' : '失败' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="errcode">{{ lastResult.errcode }}</el-descriptions-item>
            <el-descriptions-item label="接收人">{{ lastResult.touser }}</el-descriptions-item>
            <el-descriptions-item label="时间">{{ lastResult.at }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

    </el-row>
  </div>
</template>

<script setup name="Push">
import { ref, reactive, computed, onMounted } from 'vue'
import request from '@/utils/request'

const { proxy } = getCurrentInstance()

const form = reactive({
  scope: 'self',
  userIds: [],
  title: '',
  content: '',
  imageBase64: ''
})
const targets = reactive({ subscribers: [], adminUserid: '' })
const sending = ref(false)
const lastResult = ref(null)
const imgUploading = ref(false)
const imgRef = ref(null)
const imgPreview = ref('')
const imgMeta = ref('')

function pickImage() {
  imgRef.value && imgRef.value.click()
}

function onImage(e) {
  const f = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!f) return
  // 企业微信 image 消息上限 2MB，这里按 5MB 拦（base64 后约 6.7MB 请求体）
  if (f.size > 5 * 1024 * 1024) {
    proxy.$modal.msgError('图片超过 5MB，企业微信发不出去，请先压缩')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    form.imageBase64 = String(reader.result || '')
    imgPreview.value = form.imageBase64
    const sizeTxt = f.size >= 1024 * 1024
      ? (f.size / 1024 / 1024).toFixed(1) + 'MB'
      : (f.size >= 1024 ? (f.size / 1024).toFixed(0) + 'KB' : f.size + 'B')
    imgMeta.value = f.name + ' · ' + sizeTxt + ' · 将作为第二条消息发送'
  }
  reader.readAsDataURL(f)
}

function clearImage() {
  form.imageBase64 = ''
  imgPreview.value = ''
  imgMeta.value = ''
}

const previewText = computed(() => {
  const t = (form.title || '').trim()
  const c = (form.content || '').trim()
  if (!t && !c) return ''
  return (t ? `【${t}】\n\n` : '') + c
})

const byteLen = computed(() => new TextEncoder().encode(previewText.value).length)

function loadTargets() {
  request({
    url: '/system/push/targets',
    method: 'get'
  }).then(res => {
    // RuoYi 拦截器返回 { code, msg, data }
    const d = (res && res.data) ? res.data : (res || {})
    targets.subscribers = d.subscribers || []
    targets.adminUserid = d.adminUserid || ''
    if (form.scope === 'all' && !targets.subscribers.length) form.scope = 'self'
  }).catch(() => {})
}

function handleReset() {
  clearImage()
  form.title = ''
  form.content = ''
  form.userIds = []
}

function handleSend() {
  if (sending.value) return
  if (form.scope === 'ids' && !form.userIds.length) {
    proxy.$modal.msgWarning('请先选择至少一个订阅者')
    return
  }
  const c = (form.content || '').trim()
  if (!c) {
    proxy.$modal.msgWarning('请先填写正文')
    return
  }
  if (byteLen.value > 2048) {
    proxy.$modal.msgError(`内容 ${byteLen.value} 字节，超过企业微信 2048 字节上限，请精简后再发`)
    return
  }
  const who = form.scope === 'all' ? '全体成员'
    : form.scope === 'ids' ? `${form.userIds.length} 个指定订阅者`
    : '你自己'

  const extra = form.imageBase64 ? '（文字 + 图片，共两条）' : ''
  proxy.$modal.confirm(`确认把这条消息发给${who}${extra}？`).then(() => {
    sending.value = true
    return request({
      url: '/system/push/send',
      method: 'post',
      data: {
        scope: form.scope,
        userIds: form.userIds,
        title: form.title,
        content: form.content,
        imageBase64: form.imageBase64 || ''
      }
    })
  }).then(res => {
    sending.value = false
    const d = (res && res.data) ? res.data : (res || {})
    const inner = (d && d.text) ? d : ((d && d.data) ? d.data : {})
    lastResult.value = {
      ok: true,
      withImage: !!inner.withImage,
      imageOk: inner.image ? !!inner.image.ok : null,
      imageErr: inner.image ? (inner.image.errmsg || '') : '',
      errcode: d.errcode != null ? d.errcode : 0,
      touser: d.touser || form.scope,
      msgid: d.msgid || '',
      at: new Date().toLocaleString('zh-CN')
    }
    proxy.$modal.msgSuccess('发送成功，去微信看看')
  }).catch(err => {
    sending.value = false
    if (err && err !== 'cancel') {
      lastResult.value = {
        ok: false, errcode: '-', touser: form.scope, msgid: '',
        at: new Date().toLocaleString('zh-CN')
      }
    }
  })
}

onMounted(loadTargets)
</script>

<style scoped>
.img-tip {
  margin: -4px 0 10px 0;
  font-size: 12.5px;
  color: #909399;
  line-height: 1.7;
}
.img-tip b { color: #606266; }
.img-preview {
  display: flex; align-items: center; gap: 12px;
  margin: 0 0 12px 0; padding: 10px;
  border: 1px solid #ebeef5; border-radius: 8px; background: #fafafa;
}
.img-preview img {
  width: 72px; height: 72px; object-fit: cover; border-radius: 6px; flex: 0 0 72px;
}
.img-meta {
  display: flex; flex-direction: column; gap: 4px;
  font-size: 12.5px; color: #909399; min-width: 0;
}
.img-meta span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.push-page { padding: 4px; }
.panel {
  border-radius: 10px;
  margin-bottom: 16px;
  :deep(.el-card__header) { padding: 12px 16px; }
  :deep(.el-card__body) { padding: 16px; }
}
.panel-head { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: 6px; }
.panel-title { font-size: 15px; font-weight: 600; }
.panel-sub { font-size: 12px; color: #909399; }
.hint { font-size: 11px; color: #a8abb2; line-height: 1.6; margin-top: 4px; }
.warn { color: #e6a23c; margin-left: 6px; }
.mono { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11px; word-break: break-all; }


</style>
