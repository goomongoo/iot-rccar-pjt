import { ref } from "vue";
import { defineStore } from "pinia";
import axios from "axios";

const defaultAdminUser = {
  username: "SSAFY",
  useremail: "admin@ssafy.com",
  isAdmin: true,
  profileUrl: null,
  bgUrl: null,
};

export const useSystemStore = defineStore("system", () => {
  const currentUser = ref({ ...defaultAdminUser });
  const viewKey = ref(0);

  const currentWeather = ref({ city: "", temp: 0, condition: "", icon: "" });
  const weeklyForecast = ref([]);
  const hourlyForecast = ref([]);
  const locationError = ref(null);
  const isNavigating = ref(false);
  const destination = ref(null);
  const routeInfo = ref(null);
  const currentUserLocation = ref(null);

  function forceViewUpdate() {
    viewKey.value += 1;
  }

  function setCurrentUser(userData) {
    if (userData) {
      currentUser.value = { ...userData };
    } else {
      currentUser.value = { ...defaultAdminUser };
    }
  }

  function startNavigation(dest, route) {
    destination.value = dest;
    routeInfo.value = route;
    isNavigating.value = true;
  }

  function clearNavigation() {
    isNavigating.value = false;
    destination.value = null;
    routeInfo.value = null;
  }

  function getUserLocation() {
    locationError.value = null;
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        const errorMsg = "이 브라우저에서는 위치 정보가 지원되지 않습니다.";
        locationError.value = errorMsg;
        reject(new Error(errorMsg));
      } else {
        navigator.geolocation.getCurrentPosition(
          (position) =>
            resolve({
              lat: position.coords.latitude,
              lon: position.coords.longitude,
            }),
          (error) => {
            const errorMsg =
              "위치 정보를 가져올 수 없습니다. 권한을 확인해주세요.";
            locationError.value = errorMsg;
            console.error("Geolocation error:", error);
            reject(new Error(errorMsg));
          }
        );
      }
    });
  }

  async function fetchUserLocation() {
    try {
      currentUserLocation.value = await getUserLocation();
    } catch (error) {
      console.error("Store에서 위치를 가져오는 데 실패:", error);
      currentUserLocation.value = { lat: 37.566826, lon: 126.9786567 };
    }
  }

  async function fetchWeather() {
    let lat, lon;
    try {
      const coords = await getUserLocation();
      lat = coords.lat;
      lon = coords.lon;
    } catch (error) {
      console.warn(
        "사용자 위치를 가져오는 데 실패하여 기본 위치(서울)로 조회합니다."
      );
      lat = 37.5665;
      lon = 126.978;
    }
    const apiKey = import.meta.env.VITE_OPENWEATHER_API_KEY;
    if (!apiKey) {
      console.error("OpenWeatherMap API Key가 설정되지 않았습니다.");
      return;
    }

    const currentUrl = `https://api.openweathermap.org/data/2.5/weather?lat=${lat}&lon=${lon}&appid=${apiKey}&units=metric&lang=kr`;
    const forecastUrl = `https://api.openweathermap.org/data/2.5/forecast?lat=${lat}&lon=${lon}&appid=${apiKey}&units=metric&lang=kr`;

    try {
      const [currentRes, forecastRes] = await Promise.all([
        axios.get(currentUrl),
        axios.get(forecastUrl),
      ]);

      const cur = currentRes.data;
      currentWeather.value = {
        city: cur.name,
        temp: Math.round(cur.main.temp),
        condition: cur.weather[0].description,
        icon: cur.weather[0].icon,
      };

      hourlyForecast.value = forecastRes.data.list.slice(0, 5).map((item) => ({
        time: new Date(item.dt * 1000).toLocaleTimeString("ko-KR", {
          hour: "2-digit",
        }),
        icon: item.weather[0].icon,
        temp: Math.round(item.main.temp),
        humidity: item.main.humidity,
        wind: item.wind.speed,
      }));

      weeklyForecast.value = forecastRes.data.list
        .filter((item, index) => index % 8 === 0)
        .slice(0, 5)
        .map((item) => ({
          day: new Date(item.dt * 1000).toLocaleDateString("ko-KR", {
            weekday: "short",
          }),
          icon: item.weather[0].icon,
          temp: Math.round(item.main.temp),
          condition: item.weather[0].description,
        }));
    } catch (error) {
      console.error("날씨 정보를 가져오는 데 실패했습니다:", error);
    }
  }

  return {
    currentUser,
    setCurrentUser,
    viewKey,
    forceViewUpdate,
    currentWeather,
    weeklyForecast,
    hourlyForecast,
    locationError,
    fetchWeather,
    isNavigating,
    destination,
    routeInfo,
    startNavigation,
    clearNavigation,
    currentUserLocation,
    fetchUserLocation,
  };
});
