<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api } from '../api'
import { DOC_TYPES, shortDate, won } from '../format'

const router = useRouter()
const cameraInput = ref(null)
const albumInput = ref(null)

const docType = ref('')          // '' = 자동 판별
const queue = ref([])            // { file, url }
const uploading = ref(false)
const error = ref('')
const result = ref(null)         // 직전 업로드 결과
const pending = ref([])          // 검토 대기 문서
const extractor = ref('')

onMounted(async () => {
  try {
    const [meta, list] = await Promise.all([api.meta(), api.list({ status: 'pending' })])
    extractor.value = meta.extractor
    pending.value = list
  } catch (e) {
    error.value = `서버에 연결할 수 없습니다: ${e.message}`
  }
})
onBeforeUnmount(() => queue.value.forEach((q) => URL.revokeObjectURL(q.url)))

function addFiles(event) {
  const files = Array.from(event.target.files || [])
  for (const file of files) queue.value.push({ file, url: URL.createObjectURL(file) })
  event.target.value = ''   // 같은 사진을 다시 골라도 change 이벤트가 나도록
  result.value = null
  error.value = ''
}
function removeAt(i) {
  URL.revokeObjectURL(queue.value[i].url)
  queue.value.splice(i, 1)
}

const uploadLabel = computed(() =>
  uploading.value ? `읽는 중… (${queue.value.length}장)` : `${queue.value.length}장 장부에 올리기`,
)

async function upload() {
  if (!queue.value.length) return
  uploading.value = true
  error.value = ''
  try {
    const res = await api.upload(queue.value.map((q) => q.file), docType.value || null)
    queue.value.forEach((q) => URL.revokeObjectURL(q.url))
    queue.value = []
    // 한 장만 올렸으면 바로 검토 화면으로
    if (res.documents.length === 1 && !res.failures.length) {
      router.push({ name: 'review', params: { id: res.documents[0].id } })
      return
    }
    result.value = res
    pending.value = await api.list({ status: 'pending' })
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}
</script>

<template>
  <section class="hero">
    <p class="eyebrow">찍으면 장부가 되는</p>
    <h1>거래명세서, 찍어 두기만 하세요.<br />엑셀엔 제가 옮겨 적을게요.</h1>
    <p class="lead">
      고깃집에서 일할 때 정육·채소 거래명세서를 휴대폰으로 찍어 두었다가, 마감 후 엑셀에 한 줄씩 옮겨 적곤 했습니다.
      찰칵장부는 그 두 번째 단계를 없앱니다. 사진을 올리면 AI가 거래처·품목·금액을 읽고, 계정과목을 붙여 장부와 엑셀로 정리합니다.
    </p>
  </section>

  <div class="capture-grid">
    <section class="sheet stack">
      <div class="row">
        <h2 style="margin:0">사진 올리기</h2>
        <span class="spacer" />
        <span v-if="extractor" class="small muted">인식 엔진: {{ extractor === 'claude' ? 'Claude AI' : 'Tesseract OCR' }}</span>
      </div>

      <div class="segmented" role="group" aria-label="문서 종류">
        <button :class="{ on: docType === '' }" @click="docType = ''">자동</button>
        <button :class="{ on: docType === 'statement' }" @click="docType = 'statement'">거래명세서</button>
        <button :class="{ on: docType === 'receipt' }" @click="docType = 'receipt'">영수증</button>
      </div>

      <div class="pick-buttons">
        <button class="pick primary-pick" @click="cameraInput.click()">
          <span class="pick-icon" aria-hidden="true">◉</span>
          <span><strong>카메라로 찍기</strong><small>받은 자리에서 바로</small></span>
        </button>
        <button class="pick" @click="albumInput.click()">
          <span class="pick-icon" aria-hidden="true">▤</span>
          <span><strong>앨범에서 고르기</strong><small>찍어 둔 사진 여러 장</small></span>
        </button>
      </div>
      <input ref="cameraInput" type="file" accept="image/*" capture="environment" hidden @change="addFiles" />
      <input ref="albumInput" type="file" accept="image/*,.heic,.heif" multiple hidden @change="addFiles" />

      <div v-if="queue.length" class="thumbs">
        <figure v-for="(q, i) in queue" :key="q.url" class="thumb">
          <img :src="q.url" :alt="q.file.name" />
          <button class="thumb-x" :disabled="uploading" aria-label="빼기" @click="removeAt(i)">×</button>
        </figure>
      </div>

      <button class="btn ember big" :disabled="!queue.length || uploading" @click="upload">
        {{ queue.length ? uploadLabel : '사진을 먼저 골라 주세요' }}
      </button>

      <p v-if="error" class="notice error">{{ error }}</p>
      <div v-if="result" class="notice ok">
        {{ result.documents.length }}장을 읽었습니다. 오른쪽 목록에서 하나씩 확인해 주세요.
        <ul v-if="result.failures.length">
          <li v-for="f in result.failures" :key="f.filename">{{ f.filename }}: {{ f.error }}</li>
        </ul>
      </div>

      <ol class="how small muted">
        <li><b>찍기</b> — 명세서·영수증을 평평하게 놓고 네 모서리가 다 나오게</li>
        <li><b>확인</b> — AI가 읽은 값을 사진과 나란히 보며 틀린 칸만 고치기</li>
        <li><b>확정</b> — 분개가 자동으로 만들어지고, 엑셀로 한 번에 내려받기</li>
      </ol>
    </section>

    <section class="sheet">
      <div class="row" style="margin-bottom:8px">
        <h2 style="margin:0">확인 기다리는 문서</h2>
        <span class="chip pending">{{ pending.length }}</span>
      </div>
      <p v-if="!pending.length" class="empty">밀린 문서가 없습니다.</p>
      <ul v-else class="pending-list">
        <li v-for="d in pending" :key="d.id">
          <RouterLink :to="{ name: 'review', params: { id: d.id } }">
            <img :src="d.image_url" alt="" loading="lazy" />
            <span class="pending-body">
              <strong>{{ d.vendor_name || '거래처 미확인' }}</strong>
              <span class="small muted">{{ shortDate(d.issue_date) }} · {{ DOC_TYPES[d.doc_type] }}</span>
            </span>
            <span class="pending-amount">
              <span class="num">{{ won(d.total_amount) }}</span>
              <span v-if="d.warning_count" class="small warn">확인 {{ d.warning_count }}</span>
            </span>
          </RouterLink>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.hero { margin: 8px 0 28px; max-width: 760px; }
.eyebrow { margin: 0 0 6px; color: var(--ember); font-weight: 800; font-size: 13px; letter-spacing: .04em; }
.capture-grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr); gap: 20px; align-items: start; }
.pick-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.pick {
  display: flex; align-items: center; gap: 12px; text-align: left; cursor: pointer;
  padding: 16px; border-radius: var(--radius); border: 1.5px dashed var(--rule); background: #fff;
}
.pick:hover { border-color: var(--ink-soft); }
.pick strong { display: block; }
.pick small { color: var(--ink-soft); }
.pick-icon { font-size: 22px; width: 40px; height: 40px; display: grid; place-items: center; border-radius: 50%; background: #f1ebe0; }
.primary-pick { border-style: solid; border-color: var(--ink); }
.primary-pick .pick-icon { background: var(--ember); color: #fff; }
.thumbs { display: grid; grid-template-columns: repeat(auto-fill, minmax(84px, 1fr)); gap: 8px; }
.thumb { position: relative; margin: 0; aspect-ratio: 3/4; border-radius: 8px; overflow: hidden; border: 1px solid var(--line); }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.thumb-x {
  position: absolute; top: 4px; right: 4px; width: 24px; height: 24px; border-radius: 50%;
  border: 0; background: rgba(0,0,0,.6); color: #fff; cursor: pointer; line-height: 1;
}
.big { padding: 14px; font-size: 16px; }
.how { margin: 0; padding-left: 18px; display: grid; gap: 4px; }
.pending-list { list-style: none; margin: 0; padding: 0; }
.pending-list a {
  display: flex; align-items: center; gap: 12px; padding: 10px 4px; text-decoration: none;
  border-bottom: 1px solid var(--line);
}
.pending-list a:hover { background: #faf5ea; }
.pending-list img { width: 44px; height: 56px; object-fit: cover; border-radius: 6px; border: 1px solid var(--line); flex: none; }
.pending-body { display: grid; flex: 1; min-width: 0; }
.pending-body strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pending-amount { display: grid; justify-items: end; }
.warn { color: var(--amber); font-weight: 700; }
@media (max-width: 820px) {
  .capture-grid { grid-template-columns: 1fr; }
}
@media (max-width: 420px) {
  .pick-buttons { grid-template-columns: 1fr; }
}
</style>
