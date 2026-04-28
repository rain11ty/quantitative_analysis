<script setup lang="ts">
import { useToast } from '../composables/useToast';

const { toasts, removeToast } = useToast();

const iconMap: Record<string, string> = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
};
</script>

<template>
  <Teleport to="body">
    <div class="toast-container" aria-live="polite">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast-item"
          :class="'toast-' + toast.type"
          @click="removeToast(toast.id)"
        >
          <span class="toast-icon">{{ iconMap[toast.type] }}</span>
          <span class="toast-msg">{{ toast.message }}</span>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
  max-width: 380px;
}

.toast-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  font-size: .88rem;
  font-weight: 500;
  line-height: 1.4;
  cursor: pointer;
  pointer-events: auto;
  box-shadow: var(--shadow-lg);
  backdrop-filter: blur(12px);
  border: 1px solid transparent;
}

.toast-icon {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: .78rem;
  font-weight: 700;
}

.toast-success {
  background: rgba(240, 253, 246, .96);
  color: #115e59;
  border-color: #a7f3d0;
}
.toast-success .toast-icon { background: #22ab5e; color: #fff; }

.toast-error {
  background: rgba(254, 242, 242, .96);
  color: #991b1b;
  border-color: #fecaca;
}
.toast-error .toast-icon { background: #e15241; color: #fff; }

.toast-warning {
  background: rgba(255, 251, 235, .96);
  color: #92400e;
  border-color: #fcd34d;
}
.toast-warning .toast-icon { background: #f2994a; color: #fff; }

.toast-info {
  background: rgba(239, 246, 255, .96);
  color: #1e40af;
  border-color: #bfdbfe;
}
.toast-info .toast-icon { background: #1a73e8; color: #fff; }

.toast-enter-active { transition: all .3s ease; }
.toast-leave-active { transition: all .2s ease; }
.toast-enter-from { opacity: 0; transform: translateX(40px); }
.toast-leave-to { opacity: 0; transform: translateX(40px); }
</style>
