import { createRouter, createWebHistory } from 'vue-router'
import CaptureView from './views/CaptureView.vue'
import LedgerView from './views/LedgerView.vue'
import ReviewView from './views/ReviewView.vue'
import ReportView from './views/ReportView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'capture', component: CaptureView },
    { path: '/ledger', name: 'ledger', component: LedgerView },
    { path: '/documents/:id', name: 'review', component: ReviewView, props: (r) => ({ id: Number(r.params.id) }) },
    { path: '/report', name: 'report', component: ReportView },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
