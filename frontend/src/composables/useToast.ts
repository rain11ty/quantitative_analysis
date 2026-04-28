import { ref } from 'vue';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: number;
  type: ToastType;
  message: string;
  duration: number;
}

const toasts = ref<Toast[]>([]);
let nextId = 1;

export function useToast() {
  function addToast(type: ToastType, message: string, duration = 4000) {
    const id = nextId++;
    toasts.value.push({ id, type, message, duration });
    if (duration > 0) {
      setTimeout(() => removeToast(id), duration);
    }
    return id;
  }

  function removeToast(id: number) {
    toasts.value = toasts.value.filter((t) => t.id !== id);
  }

  const success = (msg: string, duration?: number) => addToast('success', msg, duration);
  const error = (msg: string, duration?: number) => addToast('error', msg, duration);
  const warning = (msg: string, duration?: number) => addToast('warning', msg, duration);
  const info = (msg: string, duration?: number) => addToast('info', msg, duration);

  return { toasts, addToast, removeToast, success, error, warning, info };
}
