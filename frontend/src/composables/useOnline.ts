import { ref, onMounted, onBeforeUnmount } from 'vue';

export function useOnline() {
  const online = ref(navigator.onLine);

  function handleOnline() { online.value = true; }
  function handleOffline() { online.value = false; }

  onMounted(() => {
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
  });

  onBeforeUnmount(() => {
    window.removeEventListener('online', handleOnline);
    window.removeEventListener('offline', handleOffline);
  });

  return { online };
}
