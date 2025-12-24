<script setup>
import { ref, onMounted, watchEffect } from 'vue';
import { useRouter } from 'vue-router';
import { useSystemStore } from '@/stores/systemStore';
import axios from 'axios';

const systemStore = useSystemStore();
const router = useRouter();

const map = ref(null);
const marker = ref(null);
const polyline = ref(null);
const currentPosMarker = ref(null);

const searchKeyword = ref('');
const searchResults = ref([]);
const selectedPlace = ref(null);
const routeIsFound = ref(false);
const fetchedRouteData = ref(null);
const isLoading = ref(false);
const mapInitialized = ref(false);

const KAKAO_REST_API_KEY = import.meta.env.VITE_KAKAO_REST_API_KEY;

onMounted(() => {
    if (window.kakao && window.kakao.maps) {
        initMap();
    } else {
        console.error("카카오맵 API가 로드되지 않았습니다.");
    }
});

const initMap = () => {
    const container = document.getElementById('map');
    const options = {
        center: new kakao.maps.LatLng(37.566826, 126.9786567),
        level: 5,
    };
    map.value = new kakao.maps.Map(container, options);

    watchEffect(() => {
        if (systemStore.currentUserLocation && map.value) {
            const { lat, lon } = systemStore.currentUserLocation;
            const currentPos = new kakao.maps.LatLng(lat, lon);

            if (!mapInitialized.value) {
                map.value.setCenter(currentPos);
                mapInitialized.value = true;
            }

            if (currentPosMarker.value) currentPosMarker.value.setMap(null);
            currentPosMarker.value = new kakao.maps.Marker({
                position: currentPos,
            });
            currentPosMarker.value.setMap(map.value);
        }
    });
};

const searchPlaces = () => {
    if (!searchKeyword.value.trim()) {
        alert('검색어를 입력해주세요.');
        return;
    }
    const ps = new kakao.maps.services.Places();
    ps.keywordSearch(searchKeyword.value, (data, status) => {
        if (status === kakao.maps.services.Status.OK) {
            searchResults.value = data;
        } else {
            searchResults.value = [];
        }
    });
};

const selectPlace = (place) => {
    selectedPlace.value = place;
    routeIsFound.value = false;
    fetchedRouteData.value = null;
    if (polyline.value) polyline.value.setMap(null);

    const moveLatLon = new kakao.maps.LatLng(place.y, place.x);
    map.value.setCenter(moveLatLon);

    if (marker.value) {
        marker.value.setMap(null);
    }
    const newMarker = new kakao.maps.Marker({ position: moveLatLon });
    newMarker.setMap(map.value);
    marker.value = newMarker;
};

const findRoute = async () => {
    if (!selectedPlace.value || !KAKAO_REST_API_KEY) return;
    if (!systemStore.currentUserLocation) {
        alert("현재 위치를 가져올 수 없습니다. 위치 권한을 확인해주세요.");
        return;
    }

    isLoading.value = true;
    routeIsFound.value = false;

    const { lon, lat } = systemStore.currentUserLocation;
    const origin = `${lon},${lat}`;
    const destination = `${selectedPlace.value.x},${selectedPlace.value.y}`;

    try {
        const response = await axios.get(
            'https://apis-navi.kakaomobility.com/v1/directions',
            {
                params: { origin, destination },
                headers: {
                    Authorization: `KakaoAK ${KAKAO_REST_API_KEY}`,
                    'Content-Type': 'application/json'
                }
            }
        );

        const route = response.data.routes[0];
        if (route) {
            fetchedRouteData.value = {
                distance: route.summary.distance,
                duration: route.summary.duration,
                path: route.sections[0].roads.flatMap(road =>
                    road.vertexes.reduce((acc, _, i) => {
                        if (i % 2 === 0) {
                            acc.push(new kakao.maps.LatLng(road.vertexes[i + 1], road.vertexes[i]));
                        }
                        return acc;
                    }, [])
                )
            };

            drawPolyline(fetchedRouteData.value.path);
            routeIsFound.value = true;
        }
    } catch (error) {
        console.error("길찾기 API 호출 실패:", error);
        alert("경로를 탐색하는 데 실패했습니다.");
    } finally {
        isLoading.value = false;
    }
};

const drawPolyline = (path) => {
    if (polyline.value) {
        polyline.value.setMap(null);
    }

    const newPolyline = new kakao.maps.Polyline({
        path: path,
        strokeWeight: 6,
        strokeColor: '#3a7bfd',
        strokeOpacity: 0.9,
        strokeStyle: 'solid',
    });
    newPolyline.setMap(map.value);
    polyline.value = newPolyline;

    const bounds = new kakao.maps.LatLngBounds();
    path.forEach(point => bounds.extend(point));
    map.value.setBounds(bounds);
};

const beginNavigation = () => {
    if (!selectedPlace.value || !routeIsFound.value || !fetchedRouteData.value) return;

    const destinationData = {
        name: selectedPlace.value.place_name,
        lat: selectedPlace.value.y,
        lon: selectedPlace.value.x,
    };

    const routeData = {
        distance: formatDistance(fetchedRouteData.value.distance),
        duration: formatDuration(fetchedRouteData.value.duration),
        path: fetchedRouteData.value.path,
    };

    systemStore.startNavigation(destinationData, routeData);
    router.push('/');
};

const formatDistance = (meters) => {
    if (meters >= 1000) {
        return `${(meters / 1000).toFixed(1)}km`;
    }
    return `${meters}m`;
};

const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    let result = '';
    if (hours > 0) result += `${hours}시간 `;
    if (minutes > 0) result += `${minutes}분`;
    return result.trim() || '1분 미만';
};
</script>

    <template>
        <div class="nav-container">
            <div class="left-panel">
                <div class="search-bar">
                    <input type="text" placeholder="장소, 주소 검색" v-model="searchKeyword" @keyup.enter="searchPlaces" />
                    <button @click="searchPlaces"><i class="bi bi-search"></i></button>
                </div>
                <ul class="results-list">
                    <li v-if="searchResults.length === 0" class="no-results">검색 결과가 없습니다.</li>
                    <li v-for="place in searchResults" :key="place.id" @click="selectPlace(place)"
                        :class="{ 'selected': selectedPlace && selectedPlace.id === place.id }">
                        <div class="place-name">{{ place.place_name }}</div>
                        <div class="place-address">{{ place.road_address_name || place.address_name }}</div>
                    </li>
                </ul>
                <div class="nav-controls">
                    <button class="route-btn" @click="findRoute" :disabled="!selectedPlace || isLoading">
                        {{ isLoading ? '경로 탐색 중...' : '길찾기' }}
                    </button>
                    <button class="start-btn" @click="beginNavigation" :disabled="!routeIsFound">안내 시작</button>
                </div>
            </div>
            <div class="right-panel">
                <div id="map" class="map-area"></div>
            </div>
        </div>
    </template>

    <style scoped>
    .nav-container {
        display: flex;
        height: 100%;
        gap: 24px;
    }

    .left-panel {
        flex-basis: 35%;
        display: flex;
        flex-direction: column;
    }

    .right-panel {
        flex-basis: 65%;
    }

    .map-area {
        width: 100%;
        height: 100%;
        border-radius: 12px;
    }

    .search-bar {
        display: flex;
        margin-bottom: 16px;
    }

    .search-bar input {
        flex-grow: 1;
        padding: 12px;
        border-radius: 8px 0 0 8px;
        border: 1px solid #2c3440;
        background-color: #2c3440;
        color: #e0e0e0;
        font-size: 16px;
    }

    .search-bar button {
        padding: 0 16px;
        border-radius: 0 8px 8px 0;
        border: none;
        background-color: #3a7bfd;
        color: white;
        cursor: pointer;
        font-size: 18px;
    }

    .results-list {
        flex-grow: 1;
        list-style: none;
        padding: 0;
        margin: 0;
        overflow-y: auto;
        background-color: #2c3440;
        border-radius: 8px;
    }

    .results-list li {
        padding: 12px 16px;
        border-bottom: 1px solid #1a2027;
        cursor: pointer;
    }

    .results-list li:hover {
        background-color: #364152;
    }

    .results-list li.selected {
        background-color: #3a7bfd;
        color: white;
    }

    .place-name {
        font-weight: bold;
    }

    .place-address {
        font-size: 12px;
        color: #a0a0a0;
    }

    li.selected .place-address {
        color: #e0e0e0;
    }

    .no-results {
        text-align: center;
        color: #a0a0a0;
        padding: 24px;
    }

    .nav-controls {
        display: flex;
        gap: 12px;
        margin-top: 16px;
    }

    .nav-controls button {
        flex-grow: 1;
        padding: 14px;
        font-size: 16px;
        font-weight: bold;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        transition: background-color 0.2s;
    }

    .nav-controls button:disabled {
        background-color: #555;
        cursor: not-allowed;
        color: #999;
    }

    .route-btn {
        background-color: #2c3440;
        color: #e0e0e0;
    }

    .start-btn {
        background-color: #255F4C;
        color: white;
    }
</style>