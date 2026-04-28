import { ref, shallowRef, type Ref } from 'vue';

export function useAsyncState<T>() {
  const data = shallowRef<T | null>(null) as Ref<T | null>;
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function run(fn: () => Promise<T>) {
    loading.value = true;
    error.value = null;
    try {
      data.value = await fn();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : '请求失败';
      error.value = msg;
      data.value = null;
    } finally {
      loading.value = false;
    }
  }

  return { data, loading, error, run };
}

export function usePagination(fetchFn: (page: number, pageSize: number) => Promise<{ total?: number; has_more?: boolean }>) {
  const page = ref(1);
  const pageSize = ref(20);
  const total = ref(0);
  const hasMore = ref(false);
  const loading = ref(false);

  async function loadPage(p?: number) {
    if (p !== undefined) page.value = p;
    loading.value = true;
    try {
      const res = await fetchFn(page.value, pageSize.value);
      total.value = res.total ?? 0;
      hasMore.value = res.has_more ?? false;
    } finally {
      loading.value = false;
    }
  }

  function reset() {
    page.value = 1;
    total.value = 0;
    hasMore.value = false;
  }

  return { page, pageSize, total, hasMore, loading, loadPage, reset };
}

export function usePollingTask(fn: () => Promise<void>, intervalMs: number) {
  let timer: ReturnType<typeof setInterval> | null = null;

  function start() {
    stop();
    fn();
    timer = setInterval(fn, intervalMs);
  }

  function stop() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  return { start, stop };
}
