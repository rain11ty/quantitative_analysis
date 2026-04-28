<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue';

const hasError = ref(false);
const errorMessage = ref('');

onErrorCaptured((err: Error) => {
  hasError.value = true;
  errorMessage.value = err.message || '未知渲染错误';
  console.error('[ErrorBoundary]', err);
  return false;
});

function retry() {
  hasError.value = false;
  errorMessage.value = '';
}
</script>

<template>
  <div v-if="hasError" class="error-boundary">
    <div class="eb-card">
      <div class="eb-icon">!</div>
      <h3>页面渲染异常</h3>
      <p class="eb-msg">{{ errorMessage }}</p>
      <button class="btn btn-primary" @click="retry">重试</button>
    </div>
  </div>
  <slot v-else />
</template>

<style scoped>
.error-boundary {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  padding: 2rem;
}
.eb-card {
  text-align: center;
  max-width: 400px;
}
.eb-icon {
  width: 56px; height: 56px;
  border-radius: 50%;
  background: #fef2f2;
  color: #e15241;
  font-size: 1.5rem; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 1rem;
}
.eb-card h3 { margin-bottom: .5rem; }
.eb-msg { color: var(--color-text-secondary); font-size: .88rem; margin-bottom: 1rem; }
</style>
