<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '../api'
import { monthRange, num, shortDate, won } from '../format'

const preset = ref('this')   // this | last | all
const summary = ref(null)
const journal = ref([])
const error = ref('')

const range = computed(() =>
  preset.value === 'all' ? { start: '', end: '' } : monthRange(preset.value === 'last' ? -1 : 0),
)

async function load() {
  error.value = ''
  try {
    ;[summary.value, journal.value] = await Promise.all([api.summary(range.value), api.journal(range.value)])
  } catch (e) {
    error.value = e.message
  }
}
watch(range, load, { immediate: true })

// 막대 길이 = 가장 큰 값 대비 비율
const share = (rows, key) => {
  const max = Math.max(1, ...rows.map((r) => r[key]))
  return (r) => `${Math.max(2, (r[key] / max) * 100)}%`
}
const vendorBar = computed(() => share(summary.value?.by_vendor || [], 'total_amount'))
const accountBar = computed(() => share(summary.value?.by_account || [], 'supply_amount'))

const journalTotals = computed(() => ({
  debit: journal.value.reduce((s, l) => s + l.debit, 0),
  credit: journal.value.reduce((s, l) => s + l.credit, 0),
}))
</script>

<template>
  <div class="row head">
    <div>
      <h1>정리</h1>
      <p class="lead" style="margin:0">확정한 문서를 거래처별·계정과목별로 모아 봅니다.</p>
    </div>
    <span class="spacer" />
    <div class="segmented">
      <button :class="{ on: preset === 'this' }" @click="preset = 'this'">이번 달</button>
      <button :class="{ on: preset === 'last' }" @click="preset = 'last'">지난달</button>
      <button :class="{ on: preset === 'all' }" @click="preset = 'all'">전체</button>
    </div>
  </div>

  <p v-if="error" class="notice error">{{ error }}</p>

  <template v-if="summary">
    <div class="stats">
      <div class="sheet stat"><span class="small muted">확정 매입 합계</span><strong class="num">{{ won(summary.total_amount) }}</strong></div>
      <div class="sheet stat"><span class="small muted">확정 문서</span><strong class="num">{{ summary.confirmed_count }}건</strong></div>
      <div class="sheet stat"><span class="small muted">검토 기다리는 문서</span><strong class="num" :class="{ warn: summary.pending_count }">{{ summary.pending_count }}건</strong></div>
    </div>

    <div class="two">
      <section class="sheet">
        <h2>거래처별</h2>
        <p v-if="!summary.by_vendor.length" class="empty">확정한 문서가 없습니다.</p>
        <ul class="bars">
          <li v-for="r in summary.by_vendor" :key="r.key">
            <div class="bar-label"><span>{{ r.key }} <span class="muted small">{{ r.count }}건</span></span><span class="num">{{ num(r.total_amount) }}</span></div>
            <div class="bar"><span :style="{ width: vendorBar(r) }" /></div>
          </li>
        </ul>
      </section>
      <section class="sheet">
        <h2>계정과목별 (공급가액)</h2>
        <p v-if="!summary.by_account.length" class="empty">확정한 품목이 없습니다.</p>
        <ul class="bars">
          <li v-for="r in summary.by_account" :key="r.key">
            <div class="bar-label"><span>{{ r.key }} <span class="muted small">{{ r.count }}품목</span></span><span class="num">{{ num(r.supply_amount) }}</span></div>
            <div class="bar account"><span :style="{ width: accountBar(r) }" /></div>
          </li>
        </ul>
      </section>
    </div>

    <section class="sheet">
      <div class="row" style="margin-bottom:8px">
        <h2 style="margin:0">분개장</h2>
        <span class="spacer" />
        <a class="btn sm" :href="api.excelUrl(range)" download>엑셀로 내려받기</a>
      </div>
      <div class="table-wrap">
        <table class="ledger-table">
          <thead>
            <tr><th style="width:84px">일자</th><th style="width:150px">계정과목</th><th class="right" style="width:110px">차변</th><th class="right" style="width:110px">대변</th><th class="hide-sm">적요</th></tr>
          </thead>
          <tbody>
            <tr v-for="(l, i) in journal" :key="i" :class="{ first: i === 0 || journal[i - 1].document_id !== l.document_id }">
              <td class="num">{{ i === 0 || journal[i - 1].document_id !== l.document_id ? shortDate(l.entry_date) : '' }}</td>
              <td :class="{ credit: l.credit }">{{ l.account }}</td>
              <td class="num right">{{ l.debit ? num(l.debit) : '' }}</td>
              <td class="num right">{{ l.credit ? num(l.credit) : '' }}</td>
              <td class="hide-sm muted small">{{ l.description }}</td>
            </tr>
            <tr v-if="!journal.length"><td colspan="5" class="empty">분개가 없습니다. 장부에서 문서를 확정하면 여기에 쌓입니다.</td></tr>
          </tbody>
          <tfoot v-if="journal.length">
            <tr><td colspan="2">합계</td><td class="num right">{{ num(journalTotals.debit) }}</td><td class="num right">{{ num(journalTotals.credit) }}</td><td class="hide-sm"></td></tr>
          </tfoot>
        </table>
      </div>
    </section>
  </template>
</template>

<style scoped>
.head { margin-bottom: 20px; align-items: flex-end; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.stat { display: grid; gap: 4px; padding: 16px 20px; }
.stat strong { font-size: 22px; letter-spacing: -0.02em; }
.stat .warn { color: var(--amber); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.bars { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
.bar-label { display: flex; justify-content: space-between; gap: 8px; font-size: 14px; margin-bottom: 4px; }
.bar { height: 8px; border-radius: 4px; background: #efe8db; overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--ember); border-radius: 4px; }
.bar.account span { background: var(--ink); }
tr.first td { border-top: 1px solid var(--rule); }
td.credit { padding-left: 32px; }
@media (max-width: 760px) {
  .stats, .two { grid-template-columns: 1fr; }
}
</style>
