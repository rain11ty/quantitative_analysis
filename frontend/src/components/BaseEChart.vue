<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as echarts from 'echarts';
import type { EChartsOption, EChartsType } from 'echarts';

const props = withDefaults(
  defineProps<{
    option: EChartsOption | null;
    height?: string;
  }>(),
  {
    height: '360px',
  },
);

const chartRef = ref<HTMLElement | null>(null);
let chart: EChartsType | null = null;

function ensureChart() {
  if (!chart && chartRef.value) {
    chart = echarts.init(chartRef.value);
  }
  return chart;
}

function handleResize() {
  chart?.resize();
}

watch(
  () => props.option,
  async (option) => {
    await nextTick();

    if (!option) {
      chart?.clear();
      return;
    }

    const instance = ensureChart();
    instance?.setOption(option, true);
    instance?.resize();
  },
  { deep: true, immediate: true },
);

onMounted(() => {
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div ref="chartRef" class="chart-root" :style="{ height }"></div>
</template>

<style scoped>
.chart-root {
  width: 100%;
  min-height: 220px;
}
</style>
