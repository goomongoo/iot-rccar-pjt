<script setup>
import { ref, onMounted, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import { useSystemStore } from '@/stores/systemStore';

const systemStore = useSystemStore();
const { isNavigating, routeInfo } = storeToRefs(systemStore);

const mapContainer = ref(null);
const map = ref(null);
let mapObjects = [];

onMounted(() => {
  if (window.kakao && window.kakao.maps) {
    initMap();
    updateMapBasedOnState();
  }
});

watch(isNavigating, async () => {
  await nextTick();
  updateMapBasedOnState();
});

const initMap = () => {
  const options = {
    center: new kakao.maps.LatLng(37.566826, 126.9786567),
    level: 7,
  };
  map.value = new kakao.maps.Map(mapContainer.value, options);
};

const clearOverlays = () => {
  mapObjects.forEach(obj => obj.setMap(null));
  mapObjects = [];
};

const updateMapBasedOnState = () => {
  if (!map.value) return;
  clearOverlays();

  if (isNavigating.value && routeInfo.value) {
    displayRoute();
  } else {
    displayCurrentLocation();
  }
};

const displayRoute = () => {
  const routePath = routeInfo.value.path;

  const polyline = new kakao.maps.Polyline({
    path: routePath,
    strokeWeight: 6,
    strokeColor: '#3a7bfd',
    strokeOpacity: 0.9,
    strokeStyle: 'solid',
  });
  polyline.setMap(map.value);
  mapObjects.push(polyline);

  const startMarker = new kakao.maps.Marker({ position: routePath[0] });
  const endMarker = new kakao.maps.Marker({ position: routePath[routePath.length - 1] });
  startMarker.setMap(map.value);
  endMarker.setMap(map.value);
  mapObjects.push(startMarker, endMarker);

  const bounds = new kakao.maps.LatLngBounds();
  routePath.forEach(point => bounds.extend(point));
  map.value.setBounds(bounds);
};

const displayCurrentLocation = () => {
  const location = systemStore.currentUserLocation || { lat: 37.566826, lon: 126.9786567 };
  const currentPosition = new kakao.maps.LatLng(location.lat, location.lon);

  const marker = new kakao.maps.Marker({
    map: map.value,
    position: currentPosition,
  });
  mapObjects.push(marker);

  map.value.setCenter(currentPosition);
  map.value.setLevel(5);
};

const cancelCurrentRoute = async () => {
  systemStore.clearNavigation();
  await nextTick();
  updateMapBasedOnState();
};
</script>

<template>
  <main class="main-content">
    <div class="left-section">
      <p class="greeting-message">오늘도 안전한 드라이빙 되세요</p>
      <div class="button-grid">
        <RouterLink to="/chatbot" class="grid-item">
          <div class="icon"><i class="bi bi-chat-dots"></i></div>
          <div>챗봇</div>
        </RouterLink>
        <RouterLink to="/log" class="grid-item">
          <div class="icon"><i class="bi bi-journal-text"></i></div>
          <div>로그</div>
        </RouterLink>
        <RouterLink to="/navigation" class="grid-item">
          <div class="icon"><i class="bi bi-compass"></i></div>
          <div>내비게이션</div>
        </RouterLink>
        <RouterLink to="/portfolio" class="grid-item">
          <div class="icon"><i class="bi bi-briefcase"></i></div>
          <div>포트폴리오</div>
        </RouterLink>
        <RouterLink to="/weather" class="grid-item">
          <div class="icon"><i class="bi bi-cloud-sun"></i></div>
          <div>날씨</div>
        </RouterLink>
        <RouterLink to="/profile" class="grid-item">
          <div class="icon"><i class="bi bi-people"></i></div>
          <div>프로필 전환</div>
        </RouterLink>
        <RouterLink to="/settings" class="grid-item">
          <div class="icon"><i class="bi bi-gear"></i></div>
          <div>설정</div>
        </RouterLink>
      </div>
    </div>
    <div class="right-section">
      <div class="widget map-widget">
        <div ref="mapContainer" class="map-placeholder"></div>

        <button v-if="isNavigating" @click="cancelCurrentRoute" class="cancel-route-btn">
          <i class="bi bi-x-lg"></i> 경로 취소
        </button>

        <div v-if="isNavigating" class="map-info">
          <span>목적지까지 {{ routeInfo.distance }}</span>
          <span>약 {{ routeInfo.duration }}</span>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.main-content {
  display: flex;
  gap: 24px;
  flex-grow: 1;
  overflow: hidden;
}

.left-section {
  flex-basis: 55%;
  display: flex;
  flex-direction: column;
}

.right-section {
  flex-basis: 45%;
  display: flex;
  flex-direction: column;
}

.greeting-message {
  font-size: 18px;
  margin-top: 0;
  margin-bottom: 20px;
}

.button-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  grid-auto-rows: 110px;
}

.grid-item {
  background-color: #2c3440;
  border: none;
  color: #e0e0e0;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  cursor: pointer;
  transition: background-color 0.2s ease;
  font-size: 14px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-decoration: none;
}

.grid-item:hover {
  background-color: #3a7bfd;
}

.grid-item .icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.map-widget {
  position: relative;
  display: flex;
  flex-direction: column;
  background-color: #255F4C;
  padding: 12px;
  flex-grow: 1;
  border-radius: 12px;
  overflow: hidden;
}

.map-placeholder {
  width: 100%;
  flex-grow: 1;
  border-radius: 8px;
  background-color: rgba(0, 0, 0, 0.1);
}

.map-info {
  width: 100%;
  display: flex;
  justify-content: space-between;
  padding: 12px 4px 4px;
  font-size: 14px;
  flex-shrink: 0;
  box-sizing: border-box;
}

.cancel-route-btn {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
  background-color: rgba(0, 0, 0, 0.6);
  color: white;
  border: none;
  border-radius: 20px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background-color 0.2s ease;
}

.cancel-route-btn:hover {
  background-color: rgba(0, 0, 0, 0.8);
}
</style>