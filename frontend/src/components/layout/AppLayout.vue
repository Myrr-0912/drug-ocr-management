<script setup lang="ts">
import SideMenu from './SideMenu.vue'
import HeaderBar from './HeaderBar.vue'
</script>

<template>
  <div class="app-layout">
    <SideMenu />
    <div class="main-wrapper">
      <HeaderBar />
      <main class="main-content">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped lang="scss">
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content {
  flex: 1;
  overflow-y: auto;
  background: #f9fafb;
  padding: 24px;
}
</style>
