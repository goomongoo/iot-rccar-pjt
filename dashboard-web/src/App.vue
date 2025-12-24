<script setup>
import { onMounted, computed } from 'vue';
import { useSystemStore } from './stores/systemStore';
import { getAuth, onAuthStateChanged } from 'firebase/auth';
import { db } from './firebase-init';
import { collection, query, where, getDocs } from 'firebase/firestore';
import DashboardHeader from '@/components/DashboardHeader.vue';
import DashboardFooter from '@/components/DashboardFooter.vue';

const systemStore = useSystemStore();

onMounted(() => {
  systemStore.fetchUserLocation();
  const auth = getAuth();
  onAuthStateChanged(auth, async (user) => {
    if (user) {
      const usersRef = collection(db, 'users');
      const q = query(usersRef, where("useremail", "==", user.email));
      const querySnapshot = await getDocs(q);
      if (!querySnapshot.empty) {
        systemStore.setCurrentUser(querySnapshot.docs[0].data());
      } else {
        systemStore.setCurrentUser(null);
      }
    } else {
      systemStore.setCurrentUser(null);
    }
  });
});

const pageStyle = computed(() => {
  const bgUrl = systemStore.currentUser?.bgUrl;
  return bgUrl ? { backgroundImage: `url(${bgUrl})` } : {};
});
</script>

<template>
  <div class="page-container" :style="pageStyle">
    <div class="tablet-frame">
      <div class="dashboard-container">
        <DashboardHeader />
        <main class="main-content-area">
          <RouterView v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" :key="systemStore.viewKey" />
            </transition>
          </RouterView>
        </main>
        <DashboardFooter />
      </div>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.page-container {
  background-color: #282c34;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 32px;
  font-family: 'Pretendard', sans-serif;
  background-size: cover;
  background-position: center;
  transition: background-image 0.5s ease-in-out;
}

.tablet-frame {
  background: #1e1e1e;
  padding: 25px;
  border-radius: 40px;
  box-shadow: 12px 12px 24px rgba(0, 0, 0, 0.7),
    inset 4px 4px 10px rgba(255, 255, 255, 0.05),
    inset -4px -4px 10px rgba(0, 0, 0, 0.8);
}

.dashboard-container {
  width: 1024px;
  height: 600px;
  background-color: #1a2027;
  border-radius: 24px;
  padding: 24px;
  color: #e0e0e0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.main-content-area {
  flex-grow: 1;
  overflow-y: auto;
}
</style>