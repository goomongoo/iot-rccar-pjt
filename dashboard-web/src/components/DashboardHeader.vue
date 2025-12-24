<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { useSystemStore } from '@/stores/systemStore.js';

const systemStore = useSystemStore();
const currentTime = ref('');
const currentDate = ref('');
let timer = null;

const weatherIconUrl = computed(() => {
    if (systemStore.currentWeather?.icon) {
        return `https://openweathermap.org/img/wn/${systemStore.currentWeather.icon}@2x.png`;
    }
    return '';
});

const updateDateTime = () => {
    const now = new Date();
    currentTime.value = now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });
    currentDate.value = now.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
};

onMounted(() => {
    updateDateTime();
    timer = setInterval(updateDateTime, 1000);
    systemStore.fetchWeather();
});

onBeforeUnmount(() => {
    clearInterval(timer);
});
</script>

<template>
    <header class="dashboard-header">
        <div class="header-left">
            <h1 class="greeting-title">안녕하세요, {{ systemStore.currentUser?.username }}님</h1>
            <div class="status-info">
                <img v-if="weatherIconUrl" :src="weatherIconUrl" alt="Weather Icon" class="weather-icon">
                <span>{{ systemStore.currentWeather?.city || '위치 로딩중...' }}</span>
                <span class="temperature">{{ systemStore.currentWeather?.temp }}°C</span>
            </div>
        </div>
        <div class="header-center">
            <p class="time">{{ currentTime }}</p>
            <p class="date">{{ currentDate }}</p>
        </div>
        <div class="header-right">
            <span>배터리</span>
            <div class="battery">
                <div class="battery-level"></div>
            </div>
        </div>
    </header>
</template>

<style scoped>
.dashboard-header {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    padding-bottom: 8px;
    margin-bottom: 12px;
    border-bottom: 1px solid #2c3440;
    flex-shrink: 0;
}

.greeting-title {
    font-size: 18px;
    font-weight: 500;
    margin: 0;
}

.status-info {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #a0a0a0;
    margin-top: 6px;
}

.weather-icon {
    width: 28px;
    height: 28px;
    margin-top: -4px;
    margin-left: -4px;
}

.header-center {
    text-align: center;
}

.time {
    font-size: 28px;
    font-weight: bold;
    margin: 0;
}

.date {
    font-size: 14px;
    color: #a0a0a0;
    margin: 0;
}

.header-right {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
    justify-self: end;
}

.battery {
    width: 28px;
    height: 14px;
    border: 2px solid #a0a0a0;
    border-radius: 4px;
    position: relative;
    padding: 1px;
}

.battery::after {
    content: '';
    position: absolute;
    right: -5px;
    top: 2px;
    width: 3px;
    height: 8px;
    background-color: #a0a0a0;
    border-radius: 0 2px 2px 0;
}

.battery-level {
    width: 85%;
    height: 100%;
    background-color: #2ecc71;
    border-radius: 2px;
}
</style>