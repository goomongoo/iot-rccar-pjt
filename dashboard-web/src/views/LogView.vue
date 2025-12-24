<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { db } from "@/firebase-init.js";
import {
    collection,
    getDocs,
    limit,
    onSnapshot,
    orderBy,
    query,
    startAfter,
} from "firebase/firestore";

/**
 * Firestore schema (from GUI Controller)
 * - telemetry collection:
 *   docId: server_time ("YYYY-MM-DD HH:MM:SS")
 *   fields: server_time + telemetry payload (ts_ms, ax, ay, az, gx, gy, gz, dist_cm, throttle, steer, ...)
 *
 * - alert collection:
 *   docId: server_time ("YYYY-MM-DD HH:MM:SS.mmm")
 *   fields: server_time + { type: "ANOMALY" | "US_BRAKE", ... }
 */

// -----------------------------
// UI State
// -----------------------------
const activeTab = ref("alert"); // "alert" | "telemetry"
const isLive = ref(true);

const loading = ref(false);
const errorMsg = ref("");

const allRows = ref([]); // raw rows for current tab
const lastDoc = ref(null); // pagination cursor
const pageSize = ref(200);

const filters = ref({
    startDate: "", // YYYY-MM-DD
    endDate: "", // YYYY-MM-DD
    type: "", // (alert) ANOMALY / US_BRAKE / ...
    keyword: "",
});

let unsubscribe = null;

// -----------------------------
// Helpers
// -----------------------------
function parseServerTimeToDate(serverTime) {
    // server_time format examples:
    // - telemetry: "2025-12-24 15:12:33"
    // - alert:     "2025-12-24 15:12:33.123"
    if (!serverTime || typeof serverTime !== "string") return null;

    // Convert "YYYY-MM-DD HH:MM:SS(.mmm)" -> "YYYY-MM-DDTHH:MM:SS(.mmm)"
    const isoLike = serverTime.replace(" ", "T");
    const d = new Date(isoLike);
    if (Number.isNaN(d.getTime())) return null;
    return d;
}

function formatServerTime(serverTime) {
    const d = parseServerTimeToDate(serverTime);
    if (!d) return String(serverTime || "");
    return d.toLocaleString("ko-KR");
}

function safeStringify(obj) {
    try {
        return JSON.stringify(obj);
    } catch {
        return String(obj);
    }
}

function orderedKeysForRow(row) {
    if (!row || typeof row !== "object") return [];

    // Common keys first
    const commonFirst = [
        "type",
        "state",
        "score",
        "threshold",
        "source",
        "dist_cm",
        "throttle",
        "steer",
        "ax",
        "ay",
        "az",
        "gx",
        "gy",
        "gz",
        "ts_ms",
        "raw",
    ];

    const ignore = new Set(["server_time"]); // header handled separately
    const presentCommon = commonFirst.filter((k) => k in row && !ignore.has(k));
    const others = Object.keys(row)
        .filter((k) => !ignore.has(k) && !commonFirst.includes(k))
        .sort();

    return [...presentCommon, ...others];
}

function rowBadgeClass(row) {
    // Alerts: based on type
    if (activeTab.value === "alert") {
        const t = String(row?.type || "").toUpperCase();
        if (t === "ANOMALY") return "badge badge-danger";
        if (t === "US_BRAKE") return "badge badge-warn";
        return "badge badge-muted";
    }

    // Telemetry: simple heuristic (if dist_cm <= 30 show warn, else normal)
    const dist = Number(row?.dist_cm);
    if (!Number.isNaN(dist) && dist <= 30) return "badge badge-warn";
    return "badge badge-ok";
}

function rowTitle(row) {
    if (activeTab.value === "alert") {
        const t = row?.type || "ALERT";
        if (t === "ANOMALY") {
            const st = row?.state ? `(${row.state})` : "";
            const score = typeof row?.score === "number" ? row.score.toFixed(6) : row?.score;
            const thr = typeof row?.threshold === "number" ? row.threshold.toFixed(6) : row?.threshold;
            return `ANOMALY ${st} score=${score} thr=${thr}`;
        }
        if (t === "US_BRAKE") return "US_BRAKE";
        return String(t);
    }

    // telemetry
    const thr = row?.throttle ?? "N/A";
    const str = row?.steer ?? "N/A";
    const dist = row?.dist_cm ?? "N/A";
    return `Telemetry  T:${thr}  S:${str}  Dist:${dist}`;
}

// -----------------------------
// Firestore Loading
// -----------------------------
function currentCollectionName() {
    return activeTab.value === "alert" ? "alert" : "telemetry";
}

function currentOrderField() {
    // GUI Controller always writes "server_time" string; orderBy on string works with this format.
    return "server_time";
}

async function loadMoreOnce() {
    errorMsg.value = "";
    loading.value = true;
    try {
        const colRef = collection(db, currentCollectionName());
        let qBase = query(colRef, orderBy(currentOrderField(), "desc"), limit(pageSize.value));

        if (lastDoc.value) {
            qBase = query(colRef, orderBy(currentOrderField(), "desc"), startAfter(lastDoc.value), limit(pageSize.value));
        }

        const snap = await getDocs(qBase);
        const docs = snap.docs;

        if (docs.length > 0) {
            lastDoc.value = docs[docs.length - 1];
        }

        const newRows = docs.map((d) => {
            const data = d.data() || {};
            // Ensure server_time exists even if only docId exists
            if (!data.server_time) data.server_time = d.id;
            return { __id: d.id, ...data };
        });

        // Append (avoid duplicates by __id)
        const seen = new Set(allRows.value.map((r) => r.__id));
        const merged = [...allRows.value];
        for (const r of newRows) {
            if (!seen.has(r.__id)) merged.push(r);
        }
        allRows.value = merged;
    } catch (e) {
        console.error(e);
        errorMsg.value = "Firestore에서 로그를 불러오지 못했습니다.";
    } finally {
        loading.value = false;
    }
}

function startLiveListener() {
    stopListener();

    errorMsg.value = "";
    loading.value = true;

    const colRef = collection(db, currentCollectionName());
    const qLive = query(colRef, orderBy(currentOrderField(), "desc"), limit(pageSize.value));

    unsubscribe = onSnapshot(
        qLive,
        (snapshot) => {
            const docs = snapshot.docs;

            if (docs.length > 0) {
                lastDoc.value = docs[docs.length - 1];
            } else {
                lastDoc.value = null;
            }

            allRows.value = docs.map((d) => {
                const data = d.data() || {};
                if (!data.server_time) data.server_time = d.id;
                return { __id: d.id, ...data };
            });

            loading.value = false;
        },
        (err) => {
            console.error(err);
            errorMsg.value = "실시간 구독(onSnapshot)에 실패했습니다.";
            loading.value = false;
        }
    );
}

function stopListener() {
    if (unsubscribe) {
        try {
            unsubscribe();
        } catch { }
    }
    unsubscribe = null;
}

async function reloadTab() {
    stopListener();
    allRows.value = [];
    lastDoc.value = null;

    if (isLive.value) {
        startLiveListener();
    } else {
        await loadMoreOnce();
    }
}

// -----------------------------
// Filtering
// -----------------------------
const filteredRows = computed(() => {
    const rows = [...allRows.value];
    const { startDate, endDate, type, keyword } = filters.value;
    const kw = (keyword || "").trim().toLowerCase();

    let startTs = null;
    let endTs = null;

    if (startDate) {
        const d = new Date(startDate);
        d.setHours(0, 0, 0, 0);
        startTs = d.getTime();
    }
    if (endDate) {
        const d = new Date(endDate);
        d.setHours(23, 59, 59, 999);
        endTs = d.getTime();
    }

    return rows.filter((r) => {
        // Date range filter by server_time
        const d = parseServerTimeToDate(r.server_time);
        const t = d ? d.getTime() : null;

        if (startTs !== null && (t === null || t < startTs)) return false;
        if (endTs !== null && (t === null || t > endTs)) return false;

        // Alert type filter
        if (activeTab.value === "alert" && type) {
            if (String(r.type || "").toUpperCase() !== String(type).toUpperCase()) return false;
        }

        // Keyword filter
        if (kw) {
            const blob = safeStringify(r).toLowerCase();
            if (!blob.includes(kw)) return false;
        }

        return true;
    });
});

// When switching tab or live mode -> reload
watch([activeTab, isLive], async () => {
    await reloadTab();
});

// -----------------------------
// Lifecycle
// -----------------------------
onMounted(async () => {
    await reloadTab();
});

onUnmounted(() => {
    stopListener();
});
</script>

<template>
    <div class="log-view-container">
        <div class="topbar">
            <div class="tabs">
                <button class="tab" :class="{ active: activeTab === 'alert' }" @click="activeTab = 'alert'">
                    Alerts (alert)
                </button>
                <button class="tab" :class="{ active: activeTab === 'telemetry' }" @click="activeTab = 'telemetry'">
                    Telemetry (telemetry)
                </button>
            </div>

            <div class="toggles">
                <label class="toggle">
                    <input type="checkbox" v-model="isLive" />
                    <span>Live</span>
                </label>

                <button class="btn" :disabled="loading" @click="reloadTab">
                    새로고침
                </button>
            </div>
        </div>

        <div class="filter-bar">
            <input type="date" v-model="filters.startDate" class="filter-input" />
            <input type="date" v-model="filters.endDate" class="filter-input" />

            <select v-if="activeTab === 'alert'" v-model="filters.type" class="filter-select">
                <option value="">모든 타입</option>
                <option value="ANOMALY">ANOMALY</option>
                <option value="US_BRAKE">US_BRAKE</option>
            </select>

            <input type="text" v-model="filters.keyword" placeholder="키워드 검색 (JSON 전체 대상)"
                class="filter-input keyword-input" />
        </div>

        <div class="statusbar">
            <div class="status-left">
                <span v-if="loading">로딩 중...</span>
                <span v-else>총 {{ filteredRows.length }}건</span>
                <span v-if="errorMsg" class="error">{{ errorMsg }}</span>
            </div>

            <div class="status-right">
                <button v-if="!isLive" class="btn" :disabled="loading" @click="loadMoreOnce">
                    더 불러오기
                </button>
            </div>
        </div>

        <div class="list">
            <div v-if="filteredRows.length === 0 && !loading" class="empty">
                표시할 로그가 없습니다.
            </div>

            <div v-for="row in filteredRows" :key="row.__id" class="card">
                <div class="card-header">
                    <span :class="rowBadgeClass(row)">
                        {{ activeTab === "alert" ? (row.type || "ALERT") : "TEL" }}
                    </span>
                    <div class="title">{{ rowTitle(row) }}</div>
                    <div class="time">{{ formatServerTime(row.server_time) }}</div>
                </div>

                <div class="card-body">
                    <div class="kv">
                        <div class="k">server_time</div>
                        <div class="v mono">{{ row.server_time }}</div>
                    </div>

                    <!-- Alert telemetry blob -->
                    <template v-if="activeTab === 'alert' && row.telemetry">
                        <div class="section-title">telemetry (attached)</div>
                        <div class="grid">
                            <div v-for="k in orderedKeysForRow(row.telemetry)" :key="`tel-${row.__id}-${k}`" class="kv">
                                <div class="k">{{ k }}</div>
                                <div class="v mono">{{ row.telemetry?.[k] ?? "N/A" }}</div>
                            </div>
                        </div>
                    </template>

                    <!-- Main fields -->
                    <div class="section-title">
                        {{ activeTab === "alert" ? "alert fields" : "telemetry fields" }}
                    </div>

                    <div class="grid">
                        <div v-for="k in orderedKeysForRow(row)" :key="`${row.__id}-${k}`" class="kv">
                            <div class="k">{{ k }}</div>
                            <div class="v mono">
                                <template v-if="k === 'raw'">
                                    {{ String(row[k] ?? "") }}
                                </template>
                                <template v-else>
                                    {{ row[k] ?? "N/A" }}
                                </template>
                            </div>
                        </div>
                    </div>

                    <details class="raw">
                        <summary>Raw JSON</summary>
                        <pre class="mono">{{ JSON.stringify(row, null, 2) }}</pre>
                    </details>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.log-view-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    gap: 12px;
    color: #e8e8e8;
}

.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 12px;
    background: #2c3440;
    border-radius: 10px;
    flex-shrink: 0;
}

.tabs {
    display: flex;
    gap: 8px;
}

.tab {
    background: #1a2027;
    color: #cfd6dd;
    border: 1px solid #3e4c5a;
    border-radius: 10px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 13px;
}

.tab.active {
    background: #3a7bfd;
    border-color: #3a7bfd;
    color: #fff;
}

.toggles {
    display: flex;
    align-items: center;
    gap: 10px;
}

.toggle {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #cfd6dd;
}

.btn {
    background: #1a2027;
    color: #e8e8e8;
    border: 1px solid #3e4c5a;
    border-radius: 10px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 13px;
}

.btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

.filter-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: #2c3440;
    border-radius: 10px;
    flex-shrink: 0;
}

.filter-input,
.filter-select {
    background: #1a2027;
    color: #e8e8e8;
    border: 1px solid #3e4c5a;
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 13px;
}

.keyword-input {
    flex: 1;
    min-width: 180px;
}

.statusbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 0 4px;
    flex-shrink: 0;
    color: #b9c1c8;
    font-size: 13px;
}

.error {
    color: #ff6b6b;
    margin-left: 10px;
}

.list {
    flex: 1;
    overflow-y: auto;
    background: #1a2027;
    border-radius: 10px;
    padding: 12px;
    -ms-overflow-style: none;
    scrollbar-width: none;
}

.list::-webkit-scrollbar {
    display: none;
}

.empty {
    text-align: center;
    padding: 48px 12px;
    color: #aab3bb;
}

.card {
    border: 1px solid #2e3a47;
    border-radius: 12px;
    padding: 12px;
    background: rgba(255, 255, 255, 0.03);
    margin-bottom: 10px;
}

.card-header {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid #2e3a47;
}

.title {
    font-weight: 600;
    color: #eaeaea;
    font-size: 13px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.time {
    font-size: 12px;
    color: #b9c1c8;
}

.card-body {
    padding-top: 10px;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.section-title {
    font-size: 12px;
    color: #b9c1c8;
    margin-top: 4px;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 6px 12px;
}

.kv {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 8px;
    align-items: start;
}

.k {
    color: #aab3bb;
    font-size: 12px;
    word-break: break-word;
}

.v {
    color: #e8e8e8;
    font-size: 12px;
    word-break: break-all;
    white-space: pre-wrap;
}

.mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.raw summary {
    cursor: pointer;
    color: #cfd6dd;
    font-size: 12px;
}

.raw pre {
    margin: 8px 0 0 0;
    padding: 10px;
    border-radius: 10px;
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid #2e3a47;
    max-height: 280px;
    overflow: auto;
}

.badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 8px;
    border-radius: 999px;
    font-size: 12px;
    border: 1px solid transparent;
}

.badge-danger {
    background: rgba(220, 53, 69, 0.12);
    border-color: rgba(220, 53, 69, 0.45);
    color: #ffb3b9;
}

.badge-warn {
    background: rgba(255, 193, 7, 0.12);
    border-color: rgba(255, 193, 7, 0.45);
    color: #ffe6a6;
}

.badge-ok {
    background: rgba(25, 135, 84, 0.12);
    border-color: rgba(25, 135, 84, 0.45);
    color: #b7f2d3;
}

.badge-muted {
    background: rgba(160, 160, 160, 0.10);
    border-color: rgba(160, 160, 160, 0.35);
    color: #d7dde3;
}
</style>
