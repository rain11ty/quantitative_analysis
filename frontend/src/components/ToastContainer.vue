<script setup lang="ts">
import { useToast } from '../composables/useToast';
const { toasts, removeToast } = useToast();
</script>

<template>
  <Teleport to="body">
    <div style="position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:6px;pointer-events:none;max-width:340px;" aria-live="polite">
      <TransitionGroup name="toast">
        <div v-for="toast in toasts" :key="toast.id"
          style="padding:10px 16px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;pointer-events:auto;backdrop-filter:blur(20px);line-height:1.4;"
          :style="{
            background: toast.type === 'success' ? 'rgba(52,199,89,.92)' : toast.type === 'error' ? 'rgba(255,59,48,.92)' : toast.type === 'warning' ? 'rgba(255,159,10,.92)' : 'rgba(0,0,0,.82)',
            color: toast.type === 'info' ? '#fff' : '#fff',
          }"
          @click="removeToast(toast.id)"
        >{{ toast.message }}</div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-enter-active { transition: all .25s ease; }
.toast-leave-active { transition: all .15s ease; }
.toast-enter-from { opacity: 0; transform: translateY(12px); }
.toast-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
