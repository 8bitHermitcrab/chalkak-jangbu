export const won = (n) => (n == null || n === '' ? '-' : `${Number(n).toLocaleString('ko-KR')}원`)
export const num = (n) => (n == null || n === '' ? '' : Number(n).toLocaleString('ko-KR'))

export const DOC_TYPES = { receipt: '영수증', statement: '거래명세서' }
export const PAYMENTS = { card: '카드', cash: '현금', transfer: '계좌이체', credit: '외상' }
export const STATUS = { pending: '검토 필요', confirmed: '확정' }

export function shortDate(d) {
  if (!d) return '날짜 없음'
  const [y, m, day] = d.split('-')
  return `${y.slice(2)}.${m}.${day}`
}

export function monthRange(offset = 0) {
  const now = new Date()
  const first = new Date(now.getFullYear(), now.getMonth() + offset, 1)
  const last = new Date(now.getFullYear(), now.getMonth() + offset + 1, 0)
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return { start: iso(first), end: iso(last) }
}

// "18,000" 같이 쉼표가 들어간 입력도 숫자로
export function toInt(v) {
  if (v === '' || v == null) return null
  const n = Number(String(v).replace(/[^\d.-]/g, ''))
  return Number.isFinite(n) ? Math.round(n) : null
}
export function toFloat(v) {
  if (v === '' || v == null) return null
  const n = Number(String(v).replace(/[^\d.-]/g, ''))
  return Number.isFinite(n) ? n : null
}
