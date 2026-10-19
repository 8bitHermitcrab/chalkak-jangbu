<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header class="topbar">
    <RouterLink to="/" class="brand">
      <span class="brand-mark" aria-hidden="true">찰</span>
      <span>찰칵장부</span>
    </RouterLink>
    <nav class="tabs">
      <RouterLink to="/">찍기</RouterLink>
      <RouterLink to="/ledger">장부</RouterLink>
      <RouterLink to="/report">정리</RouterLink>
    </nav>
  </header>
  <main class="page">
    <RouterView />
  </main>
</template>
