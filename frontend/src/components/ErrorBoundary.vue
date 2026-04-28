<script setup lang="ts">
import { ref, onErrorCaptured } from 'vue';
const hasError = ref(false);
const errorMessage = ref('');
onErrorCaptured((err: Error) => { hasError.value = true; errorMessage.value = err.message || '未知错误'; return false; });
</script>

<template>
  <div v-if="hasError" style="text-align:center;padding:64px 24px;">
    <div style="font-size:48px;margin-bottom:12px;opacity:.3;">!</div>
    <h4 style="margin-bottom:8px;">渲染异常</h4>
    <p style="color:var(--text-muted);font-size:13px;margin-bottom:16px;">{{ errorMessage }}</p>
    <button class="btn btn-primary" @click="hasError = false">重试</button>
  </div>
  <slot v-else />
</template>
