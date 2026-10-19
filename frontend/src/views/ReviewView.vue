<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import ItemsTable from '../components/ItemsTable.vue'
import { DOC_TYPES, PAYMENTS, num, toInt, won } from '../format'

const props = defineProps({ id: { type: Number, required: true } })
const router = useRouter()

const doc = ref(null)
const form = ref(null)
const accounts = ref([])
const vendors = ref([])
const busy = ref(false)
const error = ref('')
const flash = ref('')
const zoom = ref(false)
const showRaw = ref(false)
const dirty = ref(false)

const EDITABLE = ['doc_type', 'vendor_name', 'vendor_biz_no', 'issue_date', 'payment_method',
  'supply_amount', 'vat_amount', 'total_amount', 'memo', 'items']

function fill(d) {
  doc.value = d
  form.value = JSON.parse(JSON.stringify(Object.fromEntries(EDITABLE.map((k) => [k, d[k]]))))
  dirty.value = false
}

async function load() {
  error.value = ''
  flash.value = ''
  try {
    const [d, meta, v] = await Promise.all([api.get(props.id), api.meta(), api.vendors()])
    accounts.value = meta.accounts
    vendors.value = v
    fill(d)
  } catch (e) {
    error.value = e.message
  }
}
watch(() => props.id, load, { immediate: true })
watch(form, () => { dirty.value = true }, { deep: true, flush: 'sync' })

const confirmed = computed(() => doc.value?.status === 'confirmed')

// 화면에서 바로 보이는 금액 점검 (서버 검증과 같은 기준)
const localChecks = computed(() => {
  if (!form.value) return []
  const f = form.value
  const out = []
  if ((f.supply_amount || 0) + (f.vat_amount || 0) !== (f.total_amount || 0))
    out.push(`공급가액 + 세액 = ${num((f.supply_amount || 0) + (f.vat_amount || 0))}원, 합계는 ${num(f.total_amount)}원`)
  return out
})

function setAmount(key, raw) {
  form.value[key] = toInt(raw) ?? 0
}
function fillFromItems() {
  const supply = form.value.items.reduce((s, it) => s + (it.supply_amount ?? it.amount ?? 0), 0)
  const vat = form.value.items.reduce((s, it) => s + (it.vat_amount ?? 0), 0)
  form.value.supply_amount = supply
  form.value.vat_amount = vat
  form.value.total_amount = supply + vat
}
function splitVat() {
  // 합계만 아는 과세 영수증: 합계 ÷ 1.1 로 공급가액과 세액을 나눈다
  const total = form.value.total_amount || 0
  form.value.supply_amount = Math.round(total / 1.1)
  form.value.vat_amount = total - form.value.supply_amount
}

async function save() {
  busy.value = true
  error.value = ''
  try {
    fill(await api.update(props.id, form.value))
    flash.value = '저장했습니다.'
    return true
  } catch (e) {
    error.value = e.message
    return false
  } finally {
    busy.value = false
  }
}

async function confirmDoc() {
  if (dirty.value && !(await save())) return
  busy.value = true
  error.value = ''
  try {
    fill(await api.confirm(props.id))
    flash.value = '확정했습니다. 분개가 장부에 기록됐습니다.'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function nextPending() {
  const list = await api.list({ status: 'pending' })
  const next = list.find((d) => d.id !== props.id)
  router.push(next ? { name: 'review', params: { id: next.id } } : { name: 'ledger' })
}

async function unconfirm() {
  busy.value = true
  try {
    fill(await api.unconfirm(props.id))
    flash.value = '확정을 취소했습니다. 분개도 함께 지웠습니다.'
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function remove() {
  if (!confirm('이 문서와 사진을 지울까요? 되돌릴 수 없습니다.')) return
  await api.remove(props.id)
  router.push({ name: 'ledger' })
}
</script>

<template>
  <p v-if="error && !doc" class="notice error">{{ error }}</p>
  <div v-if="doc && form" class="review">
    <!-- 왼쪽: 원본 사진. 손으로 옮겨 적을 때처럼 사진과 칸을 나란히 보며 확인한다 -->
    <section class="photo-pane">
      <div class="photo" :class="{ zoom }" @click="zoom = !zoom">
        <img :src="doc.image_url" alt="올린 사진" />
      </div>
      <p class="small muted center">사진을 누르면 {{ zoom ? '원래 크기로' : '확대해서' }} 봅니다</p>
      <button class="btn ghost sm" @click="showRaw = !showRaw">{{ showRaw ? '읽은 글자 숨기기' : '읽은 글자 전체 보기' }}</button>
      <pre v-if="showRaw" class="raw">{{ doc.raw_text || '(없음)' }}</pre>
    </section>

    <!-- 오른쪽: 검토 폼 -->
    <section class="sheet stack form-pane">
      <div class="row">
        <span class="chip" :class="doc.status">{{ confirmed ? '확정' : '검토 필요' }}</span>
        <span class="small muted">
          {{ doc.extractor.startsWith('claude') ? 'Claude AI' : doc.extractor === 'tesseract' ? 'OCR' : '직접 입력' }}
          · 신뢰도 {{ Math.round(doc.confidence * 100) }}%
        </span>
        <span class="spacer" />
        <button class="btn ghost sm danger" @click="remove">삭제</button>
      </div>

      <div v-if="doc.extraction_notes.length || doc.warnings.length || localChecks.length" class="notice">
        <strong>확인해 주세요</strong>
        <ul>
          <li v-for="w in doc.extraction_notes" :key="'n' + w">{{ w }}</li>
          <li v-for="w in doc.warnings" :key="'w' + w">{{ w }}</li>
          <li v-for="w in localChecks" :key="'l' + w">{{ w }}</li>
        </ul>
      </div>

      <div class="grid-2">
        <label class="field">문서 종류
          <select v-model="form.doc_type" class="input">
            <option v-for="(label, key) in DOC_TYPES" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label class="field">거래일자
          <input v-model="form.issue_date" type="date" class="input" />
        </label>
        <label class="field">거래처
          <input v-model="form.vendor_name" class="input" list="vendor-list" placeholder="예: 한돈유통" />
          <datalist id="vendor-list"><option v-for="v in vendors" :key="v" :value="v" /></datalist>
        </label>
        <label class="field">사업자번호
          <input v-model="form.vendor_biz_no" class="input num" placeholder="000-00-00000" />
        </label>
        <label class="field">결제수단
          <select v-model="form.payment_method" class="input">
            <option :value="null">선택</option>
            <option v-for="(label, key) in PAYMENTS" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
      </div>

      <div>
        <h2>품목</h2>
        <ItemsTable v-model:items="form.items" :accounts="accounts" />
      </div>

      <div class="amounts">
        <label class="field">공급가액
          <input class="input num" inputmode="numeric" :value="num(form.supply_amount)" @change="setAmount('supply_amount', $event.target.value)" />
        </label>
        <label class="field">세액
          <input class="input num" inputmode="numeric" :value="num(form.vat_amount)" @change="setAmount('vat_amount', $event.target.value)" />
        </label>
        <label class="field">합계
          <input class="input num total" inputmode="numeric" :value="num(form.total_amount)" @change="setAmount('total_amount', $event.target.value)" />
        </label>
      </div>
      <div class="row">
        <button class="btn sm" @click="fillFromItems">품목 합계로 채우기</button>
        <button class="btn sm" @click="splitVat">합계에서 부가세 나누기 (÷1.1)</button>
      </div>

      <label class="field">메모
        <textarea v-model="form.memo" class="input" rows="2" placeholder="예: 10월분 월말 정산" />
      </label>

      <p v-if="error" class="notice error">{{ error }}</p>
      <p v-if="flash && !error" class="notice ok">{{ flash }}</p>

      <div class="row actions">
        <button class="btn" :disabled="busy || !dirty" @click="save">저장</button>
        <span class="spacer" />
        <template v-if="!confirmed">
          <button class="btn primary" :disabled="busy" @click="confirmDoc">확정하고 장부에 기록</button>
        </template>
        <template v-else>
          <button class="btn ghost" :disabled="busy" @click="unconfirm">확정 취소</button>
          <button class="btn ember" @click="nextPending">다음 문서 →</button>
        </template>
      </div>

      <div v-if="doc.journal.length">
        <h2>분개</h2>
        <table class="ledger-table">
          <thead><tr><th>계정과목</th><th class="right">차변</th><th class="right">대변</th></tr></thead>
          <tbody>
            <tr v-for="(l, i) in doc.journal" :key="i">
              <td :class="{ credit: l.credit }">{{ l.account }}</td>
              <td class="num right">{{ l.debit ? num(l.debit) : '' }}</td>
              <td class="num right">{{ l.credit ? num(l.credit) : '' }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td>합계</td>
              <td class="num right">{{ won(doc.journal.reduce((s, l) => s + l.debit, 0)) }}</td>
              <td class="num right">{{ won(doc.journal.reduce((s, l) => s + l.credit, 0)) }}</td>
            </tr>
          </tfoot>
        </table>
        <p class="small muted">{{ doc.journal[0].description }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.review { display: grid; grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr); gap: 20px; align-items: start; }
.photo-pane { position: sticky; top: 72px; display: grid; gap: 8px; justify-items: center; }
.photo {
  width: 100%; max-height: calc(100vh - 160px); overflow: auto; border-radius: var(--radius);
  background: #2b2a28; cursor: zoom-in; border: 1px solid var(--line);
}
.photo img { display: block; width: 100%; height: auto; }
.photo.zoom { cursor: zoom-out; }
.photo.zoom img { width: 220%; max-width: none; }
.center { text-align: center; margin: 0; }
.raw {
  width: 100%; max-height: 240px; overflow: auto; margin: 0; padding: 12px; border-radius: 8px;
  background: var(--sheet); border: 1px solid var(--line); font-size: 12px; white-space: pre-wrap;
}
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.amounts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.amounts .input { text-align: right; }
.total { font-weight: 800; border-color: var(--ink); }
.actions { border-top: 1px solid var(--line); padding-top: 16px; }
td.credit { padding-left: 32px; }
@media (max-width: 900px) {
  .review { grid-template-columns: 1fr; }
  .photo-pane { position: static; }
  .photo { max-height: 60vh; }
}
@media (max-width: 520px) {
  .grid-2, .amounts { grid-template-columns: 1fr; }
}
</style>
