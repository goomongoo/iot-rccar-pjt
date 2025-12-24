<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useSystemStore } from '@/stores/systemStore.js';

const systemStore = useSystemStore();
const forecastContainer = ref(null);
const activeCardIndex = ref(0);
let scrollTimeout = null;

const activateSpotlight = () => {
    const container = forecastContainer.value;
    if (!container) return;

    const cards = container.querySelectorAll('.forecast-card');
    if (cards.length === 0) return;

    const containerRect = container.getBoundingClientRect();
    const containerCenter = containerRect.left + containerRect.width / 2;

    let closestIndex = -1;
    let minDistance = Infinity;

    cards.forEach((card, index) => {
        const cardRect = card.getBoundingClientRect();
        const cardCenter = cardRect.left + cardRect.width / 2;
        const distance = Math.abs(containerCenter - cardCenter);

        if (distance < minDistance) {
            minDistance = distance;
            closestIndex = index;
        }
    });

    activeCardIndex.value = closestIndex;
};

const handleScroll = () => {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(activateSpotlight, 80);
};

onMounted(async () => {
    if (systemStore.weeklyForecast.length === 0) {
        await systemStore.fetchWeather();
    }

    await nextTick();

    const container = forecastContainer.value;
    if (container && container.firstElementChild) {
        setTimeout(() => {
            const cards = container.querySelectorAll(".forecast-card");
            if (cards.length > 0) {
                const firstCard = cards[0];
                const containerWidth = container.offsetWidth;
                const cardWidth = firstCard.offsetWidth;
                const cardOffsetLeft = firstCard.offsetLeft;
                const targetScrollLeft = cardOffsetLeft - (containerWidth - cardWidth) / 2;

                container.scrollTo({
                    left: Math.max(0, targetScrollLeft),
                    behavior: "smooth",
                });

                setTimeout(activateSpotlight, 500);
            }
        }, 150);
    }
});

onBeforeUnmount(() => {
    clearTimeout(scrollTimeout);
});
</script>

<template>
    <div class="weather-view-container">
        <div class="current-weekly-container">
            <section class="current-weather">
                <div class="temperature">{{ systemStore.currentWeather.temp || '--' }}°</div>
                <div class="location">{{ systemStore.currentWeather.city || 'Loading...' }}</div>
                <div class="condition">{{ systemStore.currentWeather.condition || '--' }}</div>
            </section>

            <section class="weekly-forecast">
                <h3>Today</h3>
                <ul>
                    <li class="day" v-for="item in systemStore.weeklyForecast" :key="item.day">
                        <span class="day-name">{{ item.day }}</span>
                        <span class="day-icon">
                            <img :src="`https://openweathermap.org/img/wn/${item.icon}@2x.png`" alt="날씨">
                        </span>
                        <span class="temp-max">{{ item.temp }}°</span>
                        <span class="condition">{{ item.condition }}</span>
                    </li>
                </ul>
            </section>
        </div>

        <section class="hourly-forecast">
            <h3>Next Hours</h3>
            <div class="forecast-cards" ref="forecastContainer" @scroll="handleScroll">
                <div class="forecast-card" v-for="(item, index) in systemStore.hourlyForecast" :key="index"
                    :class="{ active: activeCardIndex === index }">
                    <div class="time">{{ item.time }}</div>
                    <img :src="`https://openweathermap.org/img/wn/${item.icon}@2x.png`" alt="날씨">
                    <div class="temp">{{ item.temp }}°C</div>
                    <div class="info">습도 {{ item.humidity }}%</div>
                    <div class="info">풍속 {{ item.wind }}m/s</div>
                </div>
            </div>
        </section>
    </div>
</template>

<style scoped>
.weather-view-container {
    display: flex;
    gap: 20px;
    padding: 20px;
    border-radius: 12px;
    box-sizing: border-box;
    height: 100%;
    background-color: #1a2027;
}

.current-weekly-container {
    display: flex;
    flex-direction: column;
    width: 30%;
    height: 100%;
    box-sizing: border-box;
    gap: 20px;
}

.current-weather {
    background-color: #222c3a;
    border-radius: 8px;
    padding: 20px;
    text-align: center;
    box-sizing: border-box;
}

.current-weather .temperature {
    font-size: 64px;
    font-weight: bold;
}

.current-weather .location {
    margin-top: 10px;
    font-size: 18px;
    color: #a8b2c1;
}

.current-weather .condition {
    margin-top: 5px;
    font-size: 16px;
    color: #cfd7e3;
}

.weekly-forecast {
    background-color: #222c3a;
    border-radius: 8px;
    padding: 15px;
    overflow-y: auto;
    box-sizing: border-box;
    height: 100%;
    scrollbar-width: none;
    -ms-overflow-style: none;
}

.weekly-forecast::-webkit-scrollbar {
    display: none;
}

.weekly-forecast ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.weekly-forecast .day {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #2f3b50;
}

.weekly-forecast .day:last-child {
    border-bottom: none;
}

.weekly-forecast .day-name {
    font-size: 14px;
    flex: 1;
}

.weekly-forecast .day-icon img {
    width: 32px;
    height: 32px;
    margin-right: 10px;
}

.weekly-forecast .temp-max {
    font-weight: bold;
    margin-right: 5px;
}

.weekly-forecast .condition {
    font-size: 12px;
    color: #9ba8bc;
    flex-basis: 100px;
    text-align: right;
}

.hourly-forecast {
    background-color: #222c3a;
    border-radius: 8px;
    padding: 15px;
    box-sizing: border-box;
    width: 70%;
    display: flex;
    flex-direction: column;
}

.forecast-cards {
    margin-top: auto;
    margin-bottom: auto;
    display: flex;
    gap: 20px;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 30px calc(50% - 80px);
    scrollbar-width: none;
    scroll-snap-type: x mandatory;
    position: relative;
}

.forecast-cards::-webkit-scrollbar {
    display: none;
}

.forecast-card {
    flex: 0 0 auto;
    width: 160px;
    height: 220px;
    background-color: #2b3547;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    scroll-snap-align: center;
    transition: transform 0.3s ease, box-shadow 0.3s ease, background-color 0.3s ease;
    position: relative;
    z-index: 1;
}

.forecast-card.active {
    transform: scale(1.2);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.5);
    z-index: 10;
    background-color: #3a7bfd;
}

.forecast-card .time {
    font-size: 14px;
    color: #a8b2c1;
    margin-bottom: 10px;
}

.forecast-card img {
    width: 64px;
    height: 64px;
}

.forecast-card .temp {
    font-size: 24px;
    font-weight: bold;
    margin: 10px 0;
}

.forecast-card .info {
    font-size: 12px;
    color: #9ba8bc;
    margin-top: 5px;
}

h3 {
    margin-top: 0;
}
</style>