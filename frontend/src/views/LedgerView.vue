<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { DOC_TYPES, PAYMENTS, STATUS, monthRange, num, shortDate } from '../format'

const router = useRouter()
const offset = ref(0)                 // 0 = 이번 달
const allTime = ref(false)
const status = ref('')
const vendor = ref('')
const includePending = ref(false)
const docs = ref([])
const loading = ref(false)
const error = ref('')

const range = computed(() => (allTime.value ? { start: '', end: '' } : monthRange(offset.value)))
const monthLabel = computed(() => {
  if (allTime.value) return '전체 기간'
  const [y, m] = range.value.start.split('-')
  return `${y}년 ${Number(m)}월`
})

let timer
async function load() {
  loading.value = true
  error.value = ''
  try {
    docs.value = await api.list({ ...range.value, status: status.value, vendor: vendor.value.trim() })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
watch([range, status], load, { immediate: true })
watch(vendor, () => { clearTimeout(timer); timer = setTimeout(load, 250) })

const totals = computed(() => ({
  count: docs.value.length,
  amount: docs.value.reduce((s, d) => s + d.total_amount, 0),
  pending: docs.value.filter((d) => d.status === 'pending').length,
}))

const excelHref = computed(() => api.excelUrl({ ...range.value, include_pending: includePending.value || '' }))
</script>

<template>
  <div class="row head">
    <div>
      <h1>장부</h1>
      <p class="lead" style="margin:0">찍어 올린 문서가 모두 여기 쌓입니다. 확정한 것만 엑셀·분개에 들어갑니다.</p>
    </div>
  </div>

  <section class="sheet stack">
    <div class="row toolbar">
      <div class="row month">
        <button class="btn sm" :disabled="allTime" aria-label="이전 달" @click="offset--">‹</button>
        <strong class="month-label">{{ monthLabel }}</strong>
        <button class="btn sm" :disabled="allTime || offset >= 0" aria-label="다음 달" @click="offset++">›</button>
        <label class="small row"><input v-model="allTime" type="checkbox" /> 전체</label>
      </div>
      <div class="segmented">
        <button :class="{ on: status === '' }" @click="status = ''">전체</button>
        <button :class="{ on: status === 'pending' }" @click="status = 'pending'">검토 필요</button>
        <button :class="{ on: status === 'confirmed' }" @click="status = 'confirmed'">확정</button>
      </div>
      <input v-model="vendor" class="input search" placeholder="거래처 검색" />
      <span class="spacer" />
      <label class="small row"><input v-model="includePending" type="checkbox" /> 검토 전 포함</label>
      <a class="btn primary" :href="excelHref" download>엑셀로 내려받기</a>
    </div>

    <p v-if="error" class="notice error">{{ error }}</p>

    <div class="table-wrap">
      <table class="ledger-table">
        <thead>
          <tr>
            <th style="width:84px">일자</th>
            <th>거래처</th>
            <th class="hide-sm">품목</th>
            <th class="hide-sm" style="width:90px">구분</th>
            <th class="hide-sm" style="width:72px">결제</th>
            <th class="right" style="width:120px">합계</th>
            <th style="width:96px">상태</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in docs" :key="d.id" class="clickable" @click="router.push({ name: 'review', params: { id: d.id } })">
            <td class="num">{{ shortDate(d.issue_date) }}</td>
            <td><strong>{{ d.vendor_name || '거래처 미확인' }}</strong></td>
            <td class="hide-sm muted">{{ d.item_summary }}</td>
            <td class="hide-sm"><span class="chip type">{{ DOC_TYPES[d.doc_type] }}</span></td>
            <td class="hide-sm muted">{{ PAYMENTS[d.payment_method] || '-' }}</td>
            <td class="num right">{{ num(d.total_amount) }}</td>
            <td>
              <span class="chip" :class="d.status">{{ STATUS[d.status] }}</span>
              <span v-if="d.status === 'pending' && d.warning_count" class="warn-dot" :title="`확인할 곳 ${d.warning_count}개`">!</span>
            </td>
          </tr>
          <tr v-if="!docs.length && !loading">
            <td colspan="7" class="empty">이 기간에 올린 문서가 없습니다.</td>
          </tr>
        </tbody>
        <tfoot v-if="docs.length">
          <tr>
            <td colspan="2">{{ totals.count }}건<span v-if="totals.pending" class="muted small"> (검토 필요 {{ totals.pending }})</span></td>
            <td class="hide-sm" colspan="3"></td>
            <td class="num right">{{ num(totals.amount) }}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>
  </section>
</template>

<style scoped>
.head { margin-bottom: 20px; }
.toolbar { gap: 12px; }
.month { gap: 6px; }
.month-label { min-width: 96px; text-align: center; }
.search { width: 180px; }
.warn-dot {
  display: inline-grid; place-items: center; width: 18px; height: 18px; margin-left: 4px; border-radius: 50%;
  background: var(--amber); color: #fff; font-size: 11px; font-weight: 800;
}
@media (max-width: 640px) {
  .search { width: 100%; }
}
</style>
