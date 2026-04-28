<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();
</script>

<template>
  <section class="not-found-page">
    <div class="nf-card">
      <div class="nf-code">404</div>
      <h2>页面未找到</h2>
      <p class="text-muted">您访问的页面不存在或已被移除。</p>
      <div class="nf-actions">
        <button class="btn btn-primary" @click="router.push('/')">返回首页</button>
        <button class="btn btn-outline" @click="router.go(-1)">返回上一页</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.not-found-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
.nf-card {
  text-align: center;
  max-width: 400px;
}
.nf-code {
  font-size: 5rem;
  font-weight: 800;
  color: var(--color-primary);
  line-height: 1;
  margin-bottom: .5rem;
}
.nf-card h2 {
  margin-bottom: .5rem;
}
.nf-actions {
  display: flex;
  gap: .75rem;
  justify-content: center;
  margin-top: 1.5rem;
}
</style>
