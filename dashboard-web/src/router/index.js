import { createRouter, createWebHistory } from "vue-router";
import { useSystemStore } from "@/stores/systemStore";

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("../views/HomeView.vue"),
    },
    {
      path: "/portfolio",
      name: "portfolio",
      component: () => import("../views/PortfolioView.vue"),
    },
    {
      path: "/weather",
      name: "weather",
      component: () => import("../views/WeatherView.vue"),
    },
    {
      path: "/navigation",
      name: "navigation",
      component: () => import("../views/NavigationView.vue"),
    },
    {
      path: "/log",
      name: "log",
      component: () => import("../views/LogView.vue"),
    },
    {
      path: "/profile",
      name: "profile",
      component: () => import("../views/ProfileView.vue"),
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("../views/SettingsView.vue"),
    },
    {
      path: "/chatbot",
      name: "chatbot",
      component: () => import("../views/ChatbotView.vue"),
    },
  ],
});

router.afterEach((to, from) => {
  if (from.name === "profile") {
    const systemStore = useSystemStore();
    systemStore.forceViewUpdate();
  }
});

export default router;
