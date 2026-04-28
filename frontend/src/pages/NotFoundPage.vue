<script setup lang="ts">
import { useRouter } from 'vue-router';
const router = useRouter();
</script>

<template>
  <div class="empty-state" style="min-height:50vh;display:flex;align-items:center;justify-content:center;">
    <div>
      <div style="font-size:64px;font-weight:200;color:var(--text-quaternary);margin-bottom:8px;">404</div>
      <h4>页面未找到</h4>
      <p class="text-sm text-muted mb-3">您访问的页面不存在或已被移除</p>
      <div class="flex-center gap-2">
        <button class="btn btn-primary" @click="router.push('/')">返回首页</button>
        <button class="btn btn-ghost" @click="router.go(-1)">返回上页</button>
      </div>
    </div>
  </div>
</template>
