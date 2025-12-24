<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick, computed } from "vue";
import { db } from "@/firebase-init.js";
import { getAuth, onAuthStateChanged } from "firebase/auth";
import {
    collection,
    writeBatch,
    doc,
    query,
    orderBy,
    onSnapshot,
    getDocs,
    limit,
    addDoc,
    serverTimestamp,
} from "firebase/firestore";

const auth = getAuth();

// Chat history (kept as-is)
const SESSION_COL = collection(db, "chat_sessions", "default_session", "messages");
const messages = ref([]);
const messageInput = ref("");

const isCalling = ref(false);
const isTyping = ref(false);
const chatWindowRef = ref(null);
const isLoggedIn = ref(false);
const isDeleteModalVisible = ref(false);

// RAG settings
const ragN = ref(30); // recent N per collection
const maxContextChars = ref(8000); // total context clamp

let unsubscribe = null;

const GMS_KEY = import.meta.env.VITE_GMS_KEY;

// -----------------------------
// UI helper
// -----------------------------
const scrollToBottom = () => {
    nextTick(() => {
        if (chatWindowRef.value) {
            chatWindowRef.value.scrollTop = chatWindowRef.value.scrollHeight;
        }
    });
};

// -----------------------------
// Firestore chat history
// -----------------------------
const subscribeHistory = () => {
    const q = query(SESSION_COL, orderBy("createdAt", "asc"));
    unsubscribe = onSnapshot(
        q,
        (snap) => {
            if (snap.empty) {
                messages.value = [{ role: "bot", content: "안녕하세요! 무엇을 도와드릴까요?" }];
                return;
            }
            messages.value = snap.docs.map((d) => {
                const m = d.data();
                const role = m.role === "assistant" ? "bot" : m.role === "user" ? "user" : "system";
                return { role, content: m.content || "" };
            });
        },
        (err) => console.error("onSnapshot error:", err)
    );
};

const unsubscribeHistory = () => {
    if (typeof unsubscribe === "function") {
        unsubscribe();
        unsubscribe = null;
    }
};

// -----------------------------
// Delete all chat messages
// -----------------------------
const handleConfirmDelete = async () => {
    isDeleteModalVisible.value = false;
    if (!isLoggedIn.value) return;

    try {
        while (true) {
            const snap = await getDocs(query(SESSION_COL, limit(500)));
            if (snap.empty) break;

            const batch = writeBatch(db);
            snap.forEach((d) => batch.delete(doc(db, d.ref.path)));
            await batch.commit();
            await new Promise((r) => setTimeout(r, 40));
        }
    } catch (e) {
        console.error("deleteAllMessages error:", e);
        await addDoc(SESSION_COL, {
            role: "system",
            content: "삭제 중 오류가 발생했습니다.",
            createdAt: serverTimestamp(),
        });
    }
};

// -----------------------------
// RAG: load recent N docs from telemetry + alert
// -----------------------------
function clampTextTail(s, maxChars) {
    if (!s) return "";
    if (s.length <= maxChars) return s;
    return s.slice(s.length - maxChars);
}

function safeNum(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
}

function formatTelemetryLine(t) {
    // expected fields: server_time, ts_ms, ax,ay,az,gx,gy,gz,dist_cm,throttle,steer
    const parts = [];
    if (t.server_time) parts.push(`time=${t.server_time}`);
    if (t.ts_ms != null) parts.push(`ts_ms=${t.ts_ms}`);
    const dist = safeNum(t.dist_cm);
    if (dist != null) parts.push(`dist_cm=${dist}`);
    if (t.throttle != null) parts.push(`throttle=${t.throttle}`);
    if (t.steer != null) parts.push(`steer=${t.steer}`);

    const ax = safeNum(t.ax), ay = safeNum(t.ay), az = safeNum(t.az);
    const gx = safeNum(t.gx), gy = safeNum(t.gy), gz = safeNum(t.gz);

    if (ax != null || ay != null || az != null) parts.push(`a=[${ax ?? "?"},${ay ?? "?"},${az ?? "?"}]`);
    if (gx != null || gy != null || gz != null) parts.push(`g=[${gx ?? "?"},${gy ?? "?"},${gz ?? "?"}]`);

    // keep other keys minimal to reduce token waste
    return parts.join(" ");
}

function formatAlertLine(a) {
    // expected fields: server_time, type (ANOMALY/US_BRAKE), plus optional: state, score, threshold, telemetry, ...
    const parts = [];
    if (a.server_time) parts.push(`time=${a.server_time}`);
    if (a.type) parts.push(`type=${a.type}`);
    if (a.state) parts.push(`state=${a.state}`);
    if (a.score != null) parts.push(`score=${a.score}`);
    if (a.threshold != null) parts.push(`threshold=${a.threshold}`);

    // If alert includes telemetry snapshot, summarize key telemetry
    const tel = a.telemetry && typeof a.telemetry === "object" ? a.telemetry : null;
    if (tel) {
        const dist = safeNum(tel.dist_cm);
        const thr = tel.throttle ?? null;
        const str = tel.steer ?? null;
        parts.push(`tel(throttle=${thr ?? "?"}, steer=${str ?? "?"}, dist_cm=${dist ?? "?"})`);
    }
    return parts.join(" ");
}

async function fetchRecentDocs(colName, n) {
    const capped = Math.max(1, Math.min(200, Number(n) || 30));
    const colRef = collection(db, colName);
    // GUI controller writes server_time as sortable string -> orderBy works
    const q = query(colRef, orderBy("server_time", "desc"), limit(capped));
    const snap = await getDocs(q);
    return snap.docs.map((d) => {
        const data = d.data() || {};
        if (!data.server_time) data.server_time = d.id;
        return { __id: d.id, ...data };
    });
}

async function buildRagContext(n, maxChars) {
    const [telemetryDocs, alertDocs] = await Promise.all([
        fetchRecentDocs("telemetry", n),
        fetchRecentDocs("alert", n),
    ]);

    // reverse to chronological (older -> newer) so reasoning is easier
    const telLines = telemetryDocs.reverse().map(formatTelemetryLine);
    const altLines = alertDocs.reverse().map(formatAlertLine);

    const header = [
        "You are provided with recent RC-car telemetry and alert logs from Firestore.",
        "Treat them as primary facts when answering.",
        "If the logs are insufficient to answer, say so explicitly instead of guessing.",
        "When referencing events, include exact server_time strings.",
    ].join(" ");

    let body =
        `${header}\n\n` +
        `[telemetry_context]\n${telLines.join("\n")}\n[/telemetry_context]\n\n` +
        `[alert_context]\n${altLines.join("\n")}\n[/alert_context]\n`;

    body = clampTextTail(body, maxChars);
    return body;
}

function buildConversationHistoryText(maxTurns = 16) {
    // Convert Firestore chat history to plain text transcript.
    // Use the latest maxTurns user/bot messages (exclude system).
    const list = (messages.value || [])
        .filter((m) => m && (m.role === "user" || m.role === "bot"))
        .slice(-maxTurns);

    const lines = [];
    for (const m of list) {
        const role = m.role === "user" ? "User" : "Assistant";
        const c = String(m.content || "").trim();
        if (!c) continue;
        lines.push(`${role}: ${c}`);
    }
    return lines.join("\n");
}

function buildSystemPrompt() {
    // You can tune this later to match your previous function's system prompt style.
    return [
        "너는 RC Car 관제/정비를 돕는 기술 어시스턴트다.",
        "기본 응답은 한국어로 한다.",
        "사용자가 원하면 표/리스트 형태로 정리한다.",
        "RAG 컨텍스트(telemetry_context, alert_context)가 있으면 그 내용을 우선 근거로 삼는다.",
        "불확실하면 '로그가 부족하다'고 말하고, 추가로 어떤 로그가 필요한지 제안한다.",
        "추정이 필요할 때는 추정임을 명확히 표시한다.",
    ].join("\n");
}

// -----------------------------
// Gemini API call (no Firebase Function)
// -----------------------------
async function callGeminiGenerateContent(fullPrompt) {
    if (!GMS_KEY) throw new Error("VITE_GMS_KEY가 설정되지 않았습니다.");

    const url =
        `/gms/gmsapi/generativelanguage.googleapis.com/v1beta/models/` +
        `gemini-2.5-flash:generateContent?key=${encodeURIComponent(GMS_KEY)}`;

    const payload = {
        contents: [
            {
                parts: [{ text: fullPrompt }],
            },
        ],
    };

    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

    if (!res.ok) {
        const t = await res.text().catch(() => "");
        throw new Error(`Gemini HTTP ${res.status} ${t}`.slice(0, 500));
    }

    const json = await res.json();

    // Typical response: { candidates:[ { content:{ parts:[{text:"..."}] } } ] }
    const text =
        json?.candidates?.[0]?.content?.parts?.map((p) => p?.text).filter(Boolean).join("") ||
        "";

    if (!text.trim()) {
        throw new Error("Gemini 응답에서 텍스트를 추출하지 못했습니다.");
    }
    return text;
}

// -----------------------------
// Send
// -----------------------------
const send = async () => {
    const text = messageInput.value.trim();
    if (!text || isCalling.value || !isLoggedIn.value) return;

    // Optimistic UI (snapshot will also catch up)
    messageInput.value = "";
    isCalling.value = true;
    isTyping.value = true;

    try {
        // Save user message first
        await addDoc(SESSION_COL, {
            role: "user",
            content: text,
            createdAt: serverTimestamp(),
            meta: { source: "client" },
        });

        // Build RAG context from Firestore telemetry/alert
        const ragCtx = await buildRagContext(ragN.value, maxContextChars.value);

        // Add recent chat transcript
        const historyText = buildConversationHistoryText(16);

        // Final prompt
        const systemPrompt = buildSystemPrompt();

        const fullPrompt = [
            `[system]\n${systemPrompt}\n[/system]\n`,
            ragCtx ? `${ragCtx}\n` : "",
            historyText ? `[chat_history]\n${historyText}\n[/chat_history]\n` : "",
            `[user_question]\n${text}\n[/user_question]\n`,
            "위 컨텍스트를 바탕으로 답변하라. 컨텍스트에 없는 사실은 단정하지 말라.",
        ].join("\n");

        const answer = await callGeminiGenerateContent(fullPrompt);

        // Save assistant message
        await addDoc(SESSION_COL, {
            role: "assistant",
            content: answer,
            createdAt: serverTimestamp(),
            meta: { source: "gemini", rag: { telemetry: ragN.value, alert: ragN.value } },
        });
    } catch (err) {
        console.error(err);
        await addDoc(SESSION_COL, {
            role: "system",
            content: `요청 중 오류가 발생했어요: ${String(err)}`,
            createdAt: serverTimestamp(),
        });
    } finally {
        isCalling.value = false;
        isTyping.value = false;
    }
};

// -----------------------------
// STT (keep existing)
// -----------------------------
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
const isRecording = ref(false);
const isSttSupported = !!SR;

const toggleSTT = () => {
    if (!SR || isCalling.value) return;
    if (isRecording.value) stopSTT();
    else startSTT();
};

const startSTT = () => {
    if (isRecording.value) return;
    recognition = new SR();
    recognition.lang = "ko-KR";
    recognition.interimResults = true;
    recognition.continuous = true;

    let finalTranscript = "";
    recognition.onstart = () => {
        isRecording.value = true;
    };
    recognition.onresult = (event) => {
        let interimTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
            else interimTranscript += event.results[i][0].transcript;
        }
        messageInput.value = finalTranscript + interimTranscript;
    };
    recognition.onerror = (event) => {
        console.warn("STT error:", event.error);
    };
    recognition.onend = () => {
        stopSTT();
    };
    recognition.start();
};

const stopSTT = () => {
    if (recognition) recognition.stop();
    recognition = null;
    isRecording.value = false;
};

// -----------------------------
// Lifecycle
// -----------------------------
onMounted(() => {
    onAuthStateChanged(auth, (user) => {
        isLoggedIn.value = !!user;
    });
    subscribeHistory();
});

onBeforeUnmount(() => {
    unsubscribeHistory();
    if (isRecording.value) stopSTT();
});

watch(messages, scrollToBottom, { deep: true });
</script>

<template>
    <div class="chatbot-container">
        <div class="chatbot-header">
            <h3 class="title">Chatbot</h3>

            <div class="header-actions">
                <div class="rag-controls" v-if="isLoggedIn">
                    <label class="rag-label">RAG N</label>
                    <select v-model.number="ragN" class="rag-select" :disabled="isCalling">
                        <option :value="10">10</option>
                        <option :value="20">20</option>
                        <option :value="30">30</option>
                        <option :value="50">50</option>
                        <option :value="100">100</option>
                    </select>
                </div>

                <button v-if="isLoggedIn" @click="isDeleteModalVisible = true" class="header-btn" title="채팅 기록 삭제">
                    <i class="bi bi-trash3"></i> 삭제
                </button>
            </div>
        </div>

        <div class="chat-window" ref="chatWindowRef" aria-live="polite">
            <div v-for="(msg, index) in messages" :key="index" :class="['message', msg.role]">
                {{ msg.content }}
            </div>
        </div>

        <template v-if="isLoggedIn">
            <div class="typing" :class="{ hidden: !isTyping }" aria-hidden="true" aria-label="답변 생성 중">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>

            <div class="chat-input-area">
                <button class="icon-btn mic-btn" @click="toggleSTT" :class="{ recording: isRecording }"
                    :title="isSttSupported ? '음성 입력' : '음성 입력 미지원'" :disabled="!isSttSupported || isCalling">
                    <i class="bi bi-mic-fill"></i>
                </button>

                <input type="text" v-model="messageInput" placeholder="메시지를 입력하세요..." :disabled="isCalling"
                    @keydown.enter.prevent="send" />

                <button class="icon-btn send-btn" @click="send" title="보내기"
                    :disabled="isCalling || !messageInput.trim()">
                    <i class="bi bi-send-fill"></i>
                </button>
            </div>
        </template>

        <div v-if="isDeleteModalVisible" class="modal-overlay">
            <div class="modal-content">
                <h2>기록 삭제</h2>
                <p>모든 채팅 기록을 삭제하시겠습니까?<br />이 작업은 되돌릴 수 없습니다.</p>
                <div class="modal-buttons">
                    <button @click="isDeleteModalVisible = false" class="btn-cancel">취소</button>
                    <button @click="handleConfirmDelete" class="btn-delete">삭제</button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.chatbot-container {
    width: 100%;
    height: 100%;
    color: #e0e0e0;
    background-color: #2c3440;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.chatbot-header {
    padding: 16px 20px;
    border-bottom: 1px solid #3e4c5a;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
}

.chatbot-header .title {
    font-size: 18px;
    font-weight: 500;
    margin: 0;
}

.header-actions {
    display: flex;
    align-items: center;
    gap: 10px;
}

.rag-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid #3e4c5a;
    border-radius: 10px;
    padding: 6px 10px;
}

.rag-label {
    font-size: 12px;
    color: #cfd6dd;
}

.rag-select {
    background: #1a2027;
    color: #e0e0e0;
    border: 1px solid #3e4c5a;
    border-radius: 8px;
    height: 28px;
    padding: 0 8px;
    font-size: 12px;
    outline: none;
}

.header-btn {
    background: #3e4c5a;
    border: none;
    color: #e0e0e0;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    display: flex;
    align-items: center;
    gap: 6px;
}

.header-btn:hover {
    background: #555e68;
}

.chat-window {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
    -ms-overflow-style: none;
    scrollbar-width: none;
}

.chat-window::-webkit-scrollbar {
    display: none;
}

.message {
    max-width: 70%;
    padding: 10px 14px;
    border-radius: 10px;
    font-size: 15px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
}

.message.bot {
    background-color: #1a2027;
    align-self: flex-start;
}

.message.user {
    background-color: #3a7bfd;
    color: #fff;
    align-self: flex-end;
}

.message.system {
    background: #3e4c5a;
    color: #a0a0a0;
    font-style: italic;
    align-self: center;
    font-size: 13px;
}

.typing {
    height: 24px;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 20px 10px 20px;
    flex-shrink: 0;
}

.hidden {
    display: none;
}

.dot {
    width: 7px;
    height: 7px;
    background: #a0a0a0;
    border-radius: 50%;
    animation: blink 1.2s infinite ease-in-out;
}

.dot:nth-child(2) {
    animation-delay: 0.2s;
}

.dot:nth-child(3) {
    animation-delay: 0.4s;
}

@keyframes blink {

    0%,
    80%,
    100% {
        opacity: 0.4;
        transform: scale(0.9);
    }

    40% {
        opacity: 1;
        transform: scale(1);
    }
}

.chat-input-area {
    padding: 12px 20px;
    border-top: 1px solid #3e4c5a;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
}

.chat-input-area input {
    flex: 1;
    height: 40px;
    border-radius: 8px;
    border: 1px solid #3e4c5a;
    background-color: #1a2027;
    color: #e0e0e0;
    outline: none;
    padding: 0 15px;
    font-size: 15px;
}

.chat-input-area input::placeholder {
    color: #a0a0a0;
}

.icon-btn {
    background: #3e4c5a;
    border: none;
    color: #e0e0e0;
    width: 40px;
    height: 40px;
    border-radius: 8px;
    cursor: pointer;
}

.icon-btn:hover {
    background: #555e68;
}

.mic-btn.recording {
    background: #d9534f;
}

.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0, 0, 0, 0.5);
    display: flex;
    justify-content: center;
    align-items: center;
}

.modal-content {
    background-color: #2c3440;
    padding: 30px;
    border-radius: 12px;
    text-align: center;
    width: 320px;
    border: 1px solid #3e4c5a;
}

.modal-buttons {
    display: flex;
    justify-content: center;
    gap: 10px;
    margin-top: 20px;
}

.btn-cancel,
.btn-delete {
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    cursor: pointer;
    font-size: 14px;
    color: #fff;
}

.btn-cancel {
    background: #6c757d;
}

.btn-delete {
    background: #d9534f;
}
</style>
