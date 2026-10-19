<script setup>
import { computed } from 'vue'
import { num, toFloat, toInt } from '../format'

const props = defineProps({
  items: { type: Array, required: true },
  accounts: { type: Array, default: () => [] },
  readonly: { type: Boolean, default: false },
})
const emit = defineEmits(['update:items'])

function patch(i, key, raw) {
  const items = props.items.map((it) => ({ ...it }))
  const it = items[i]
  if (key === 'name' || key === 'spec' || key === 'account') it[key] = raw
  else if (key === 'quantity') it.quantity = toFloat(raw)
  else it[key] = toInt(raw)

  // 수량·단가를 고치면 공급가액을 다시 계산한다 (손으로 옮겨 적을 때 하던 계산)
  if ((key === 'quantity' || key === 'unit_price') && it.quantity != null && it.unit_price != null) {
    it.supply_amount = Math.round(it.quantity * it.unit_price)
  }
  if (it.supply_amount != null) it.amount = it.supply_amount + (it.vat_amount || 0)
  emit('update:items', items)
}

function addRow() {
  emit('update:items', [
    ...props.items,
    { name: '', spec: null, quantity: null, unit_price: null, supply_amount: null, vat_amount: null, amount: null, account: props.accounts[0] || null },
  ])
}
function removeRow(i) {
  emit('update:items', props.items.filter((_, idx) => idx !== i))
}

const mismatch = (it) =>
  it.quantity != null && it.unit_price != null && it.supply_amount != null &&
  Math.abs(Math.round(it.quantity * it.unit_price) - it.supply_amount) > 10

const totals = computed(() => ({
  supply: props.items.reduce((s, it) => s + (it.supply_amount ?? it.amount ?? 0), 0),
  vat: props.items.reduce((s, it) => s + (it.vat_amount ?? 0), 0),
}))
defineExpose({ totals })
</script>

<template>
  <div class="table-wrap">
    <table class="ledger-table items">
      <thead>
        <tr>
          <th style="min-width:140px">품목</th>
          <th class="hide-sm" style="width:80px">규격</th>
          <th class="right" style="width:70px">수량</th>
          <th class="right" style="width:100px">단가</th>
          <th class="right" style="width:110px">공급가액</th>
          <th class="right" style="width:90px">세액</th>
          <th style="width:150px">계정과목</th>
          <th v-if="!readonly" style="width:36px"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(it, i) in items" :key="i" :class="{ bad: mismatch(it) }">
          <td><input class="cell" :value="it.name" :readonly="readonly" placeholder="품목명" @change="patch(i, 'name', $event.target.value)" /></td>
          <td class="hide-sm"><input class="cell" :value="it.spec" :readonly="readonly" @change="patch(i, 'spec', $event.target.value)" /></td>
          <td><input class="cell num right" inputmode="decimal" :value="it.quantity" :readonly="readonly" @change="patch(i, 'quantity', $event.target.value)" /></td>
          <td><input class="cell num right" inputmode="numeric" :value="num(it.unit_price)" :readonly="readonly" @change="patch(i, 'unit_price', $event.target.value)" /></td>
          <td>
            <input class="cell num right" inputmode="numeric" :value="num(it.supply_amount ?? it.amount)" :readonly="readonly"
                   :title="mismatch(it) ? '수량×단가와 다릅니다' : ''" @change="patch(i, 'supply_amount', $event.target.value)" />
          </td>
          <td><input class="cell num right" inputmode="numeric" :value="num(it.vat_amount)" :readonly="readonly" @change="patch(i, 'vat_amount', $event.target.value)" /></td>
          <td>
            <select class="cell" :value="it.account" :disabled="readonly" @change="patch(i, 'account', $event.target.value)">
              <option v-for="a in accounts" :key="a" :value="a">{{ a }}</option>
            </select>
          </td>
          <td v-if="!readonly"><button class="btn ghost sm" aria-label="줄 삭제" @click="removeRow(i)">×</button></td>
        </tr>
        <tr v-if="!items.length">
          <td :colspan="readonly ? 7 : 8" class="muted small">읽힌 품목이 없습니다. 품목 없이 합계만 확정해도 됩니다.</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <td>품목 합계</td>
          <td class="hide-sm"></td>
          <td></td>
          <td></td>
          <td class="num right">{{ num(totals.supply) }}</td>
          <td class="num right">{{ num(totals.vat) }}</td>
          <td colspan="2"></td>
        </tr>
      </tfoot>
    </table>
  </div>
  <button v-if="!readonly" class="btn sm" style="margin-top:8px" @click="addRow">+ 품목 추가</button>
</template>

<style scoped>
.items td { padding: 4px; }
.cell {
  width: 100%; border: 1px solid transparent; background: transparent; padding: 6px 6px; border-radius: 6px;
}
.cell:hover:not([readonly]):not(:disabled) { border-color: var(--line); background: #fff; }
.cell:focus { outline: none; border-color: var(--ember); background: #fff; }
select.cell { appearance: auto; }
tr.bad td { background: var(--amber-soft); }
</style>
