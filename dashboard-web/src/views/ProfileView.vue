<script setup>
import { ref, onMounted, nextTick, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { db } from '@/firebase-init';
import { getAuth, signInWithEmailAndPassword, signOut, createUserWithEmailAndPassword } from 'firebase/auth';
import { collection, getDocs, query, where, setDoc, doc } from 'firebase/firestore';
import { useSystemStore } from '@/stores/systemStore';

const systemStore = useSystemStore();
const router = useRouter();
const profiles = ref([]);
const isLoading = ref(true);
const authLoading = ref(false);
const selectedProfile = ref(null);
const password = ref('');
const isPasswordModalVisible = ref(false);
const passwordInputRef = ref(null);
const isMessageModalVisible = ref(false);
const modalMessage = ref('');
const loginSuccess = ref(false);
const isRegisterModalVisible = ref(false);
const registerLoading = ref(false);
const newProfile = ref({
    username: '',
    useremail: '',
    password: '',
    passwordConfirm: ''
});
const emailCheck = ref({
    status: 'unchecked',
    message: ''
});
const registerUsernameInputRef = ref(null);
const registerError = ref('');

watch(newProfile, () => {
    registerError.value = '';
}, { deep: true });


onMounted(async () => {
    fetchProfiles();
});

const fetchProfiles = async () => {
    try {
        isLoading.value = true;
        const usersCollection = collection(db, 'users');
        const userSnapshot = await getDocs(usersCollection);
        const firestoreProfiles = userSnapshot.docs.map(doc => doc.data());
        const adminProfile = {
            username: "SSAFY", useremail: "admin@ssafy.com", isAdmin: true, profileUrl: null, bgUrl: null
        };
        profiles.value = [adminProfile, ...firestoreProfiles];
    } catch (error) {
        console.error("Firestore에서 사용자 목록을 가져오는 데 실패했습니다:", error);
        modalMessage.value = "프로필을 불러오는 데 실패했습니다.";
        isMessageModalVisible.value = true;
    } finally {
        isLoading.value = false;
    }
}

const handleProfileSelect = async (profile) => {
    if (profile.useremail === systemStore.currentUser?.useremail) {
        modalMessage.value = `이미 ${profile.username}님으로 로그인되어 있습니다.`;
        isMessageModalVisible.value = true;
        return;
    }

    if (profile.username === 'SSAFY') {
        const auth = getAuth();
        if (auth.currentUser) {
            await signOut(auth);
        }
        modalMessage.value = "SSAFY 관리자 프로필로 전환되었습니다.";
        isMessageModalVisible.value = true;
        loginSuccess.value = true;
    } else {
        openPasswordModal(profile);
    }
};

const openPasswordModal = (profile) => {
    selectedProfile.value = profile;
    isPasswordModalVisible.value = true;
    nextTick(() => {
        passwordInputRef.value?.focus();
    });
};

const openRegisterModal = () => {
    isRegisterModalVisible.value = true;
    nextTick(() => {
        registerUsernameInputRef.value?.focus();
    });
};

const closeModals = () => {
    isPasswordModalVisible.value = false;
    isMessageModalVisible.value = false;
    isRegisterModalVisible.value = false;
    password.value = '';
    selectedProfile.value = null;
    modalMessage.value = '';
    authLoading.value = false;
    registerLoading.value = false;

    newProfile.value = { username: '', useremail: '', password: '', passwordConfirm: '' };
    emailCheck.value = { status: 'unchecked', message: '' };
    registerError.value = '';

    if (loginSuccess.value) {
        router.push('/');
        loginSuccess.value = false;
    }
};

const handleLogin = async () => {
    if (!password.value) {
        alert('비밀번호를 입력해주세요.');
        return;
    }
    authLoading.value = true;
    const auth = getAuth();
    try {
        await signInWithEmailAndPassword(auth, selectedProfile.value.useremail, password.value);

        isPasswordModalVisible.value = false;
        modalMessage.value = `${selectedProfile.value.username}님으로 프로필이 변경되었습니다.`;
        isMessageModalVisible.value = true;
        loginSuccess.value = true;

    } catch (error) {
        console.error("Firebase 인증 실패:", error);
        password.value = '';
        modalMessage.value = "비밀번호가 올바르지 않습니다. 다시 시도해주세요.";
        isPasswordModalVisible.value = false;
        isMessageModalVisible.value = true;
    } finally {
        authLoading.value = false;
    }
};

const checkEmailDuplicate = async () => {
    if (!newProfile.value.useremail) {
        emailCheck.value = { status: 'unchecked', message: '' };
        return;
    }
    emailCheck.value = { status: 'checking', message: '이메일 중복 확인 중...' };
    try {
        const usersRef = collection(db, 'users');
        const q = query(usersRef, where("useremail", "==", newProfile.value.useremail));
        const querySnapshot = await getDocs(q);
        if (!querySnapshot.empty) {
            emailCheck.value = { status: 'invalid', message: '이미 사용 중인 이메일입니다.' };
        } else {
            emailCheck.value = { status: 'valid', message: '사용 가능한 이메일입니다.' };
        }
    } catch (error) {
        console.error("이메일 확인 실패:", error);
        emailCheck.value = { status: 'invalid', message: '확인 중 오류가 발생했습니다.' };
    }
};

const passwordsMatch = computed(() => {
    if (!newProfile.value.password || !newProfile.value.passwordConfirm) {
        return true;
    }
    return newProfile.value.password === newProfile.value.passwordConfirm;
});

const handleRegister = async () => {
    registerError.value = '';

    if (!newProfile.value.username || !newProfile.value.useremail || !newProfile.value.password) {
        registerError.value = '모든 필드를 입력해주세요.';
        return;
    }
    if (emailCheck.value.status !== 'valid') {
        registerError.value = '사용 가능한 이메일을 입력해주세요.';
        return;
    }
    if (!passwordsMatch.value) {
        registerError.value = '비밀번호가 일치하지 않습니다.';
        return;
    }

    registerLoading.value = true;
    const auth = getAuth();
    try {
        const userCredential = await createUserWithEmailAndPassword(auth, newProfile.value.useremail, newProfile.value.password);
        const user = userCredential.user;

        const newUserDoc = {
            username: newProfile.value.username,
            useremail: newProfile.value.useremail,
            isAdmin: false,
            profileUrl: null,
            bgUrl: null,
        };
        await setDoc(doc(db, "users", user.uid), newUserDoc);

        isRegisterModalVisible.value = false;
        modalMessage.value = `회원가입이 완료되었습니다. ${newProfile.value.username}님 환영합니다!`;
        isMessageModalVisible.value = true;

        fetchProfiles();

    } catch (error) {
        console.error("회원가입 실패:", error);
        if (error.code === 'auth/email-already-in-use') {
            registerError.value = "이미 가입된 이메일입니다.";
        } else if (error.code === 'auth/weak-password') {
            registerError.value = "비밀번호는 6자 이상이어야 합니다.";
        } else {
            registerError.value = "회원가입에 실패했습니다. 다시 시도해주세요.";
        }
    } finally {
        registerLoading.value = false;
    }
};
</script>

<template>
    <div class="profile-view-wrapper">
        <div class="profile-view-container">
            <h1 class="title">프로필을 선택하세요</h1>
            <div v-if="isLoading" class="loading-spinner"></div>
            <div v-else class="profile-grid">
                <div v-for="profile in profiles" :key="profile.useremail" class="profile-card"
                    @click="handleProfileSelect(profile)">
                    <div class="profile-image-wrapper">
                        <img v-if="profile.profileUrl" :src="profile.profileUrl" alt="Profile" />
                        <i v-else class="bi bi-person-circle default-icon"></i>
                    </div>
                    <span class="username">{{ profile.username }}</span>
                    <span class="useremail">{{ profile.useremail }}</span>
                </div>
                <div class="profile-card add-profile" @click="openRegisterModal">
                    <div class="profile-image-wrapper">
                        <i class="bi bi-plus-lg"></i>
                    </div>
                    <span class="username">회원가입</span>
                </div>
            </div>
        </div>

        <div v-if="isPasswordModalVisible" class="modal-overlay" @click.self="closeModals">
            <div class="modal-content">
                <h2>비밀번호 입력</h2>
                <p>{{ selectedProfile.username }} 계정으로 로그인합니다.</p>
                <input type="password" v-model="password" placeholder="비밀번호" @keyup.enter="handleLogin"
                    class="password-input" ref="passwordInputRef" />
                <div class="modal-buttons">
                    <button @click="closeModals" class="btn-cancel">취소</button>
                    <button @click="handleLogin" class="btn-confirm" :disabled="authLoading">
                        {{ authLoading ? '인증 중...' : '확인' }}
                    </button>
                </div>
            </div>
        </div>

        <div v-if="isMessageModalVisible" class="modal-overlay">
            <div class="modal-content">
                <h2>알림</h2>
                <p>{{ modalMessage }}</p>
                <div class="modal-buttons">
                    <button @click="closeModals" class="btn-confirm">확인</button>
                </div>
            </div>
        </div>

        <div v-if="isRegisterModalVisible" class="modal-overlay" @click.self="closeModals">
            <div class="modal-content">
                <h2>회원가입</h2>
                <div class="register-form">
                    <input type="text" v-model="newProfile.username" placeholder="이름" class="password-input"
                        ref="registerUsernameInputRef" />
                    <div>
                        <input type="email" v-model="newProfile.useremail" placeholder="이메일 주소" class="password-input"
                            @blur="checkEmailDuplicate" />
                        <p v-if="emailCheck.message" :class="`email-check-message ${emailCheck.status}`">{{
                            emailCheck.message }}</p>
                    </div>
                    <input type="password" v-model="newProfile.password" placeholder="비밀번호" class="password-input" />
                    <div>
                        <input type="password" v-model="newProfile.passwordConfirm" placeholder="비밀번호 확인"
                            class="password-input" />
                        <p v-if="!passwordsMatch && newProfile.passwordConfirm" class="password-match-error">비밀번호가 일치하지
                            않습니다.</p>
                    </div>
                </div>

                <p v-if="registerError" class="register-error-message">{{ registerError }}</p>

                <div class="modal-buttons">
                    <button @click="closeModals" class="btn-cancel">취소</button>
                    <button @click="handleRegister" class="btn-confirm"
                        :disabled="registerLoading || emailCheck.status !== 'valid' || !passwordsMatch || !newProfile.password">
                        {{ registerLoading ? '가입 중...' : '회원가입' }}
                    </button>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.profile-view-wrapper {
    height: 100%;
    width: 100%;
}

.profile-view-container {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    height: 100%;
    color: #e0e0e0;
}

.title {
    font-size: 28px;
    font-weight: 500;
    margin-bottom: 40px;
}

.profile-grid {
    display: flex;
    gap: 30px;
}

.profile-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    text-align: center;
}

.profile-image-wrapper {
    width: 150px;
    height: 150px;
    border-radius: 12px;
    background-color: #3a7bfd;
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: hidden;
    border: 4px solid transparent;
    transition: border-color 0.2s;
}

.profile-card:hover .profile-image-wrapper {
    border-color: #e0e0e0;
}

.profile-image-wrapper img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.default-icon,
.add-profile i {
    font-size: 80px;
    color: #1a2027;
}

.add-profile .profile-image-wrapper {
    background-color: #2c3440;
}

.add-profile i {
    color: #a0a0a0;
}

.username {
    font-size: 18px;
    font-weight: 500;
    color: #e0e0e0;
}

.useremail {
    font-size: 14px;
    color: #a0a0a0;
}

.modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 1000;
}

.modal-content {
    background-color: #2c3440;
    padding: 30px;
    border-radius: 12px;
    width: 400px;
    text-align: center;
}

h2 {
    margin-top: 0;
    margin-bottom: 24px;
}

p {
    margin-bottom: 24px;
    color: #a0a0a0;
}

.password-input {
    width: 100%;
    padding: 12px;
    border-radius: 6px;
    border: 1px solid #3e4c5a;
    background-color: #1a2027;
    color: #e0e0e0;
    font-size: 16px;
    box-sizing: border-box;
}

.modal-buttons {
    display: flex;
    gap: 12px;
    justify-content: center;
    margin-top: 24px;
}

button {
    padding: 10px 20px;
    border-radius: 6px;
    border: none;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    min-width: 100px;
}

.btn-cancel {
    background-color: #555e68;
    color: #e0e0e0;
}

.btn-confirm {
    background-color: #3a7bfd;
    color: white;
}

.btn-confirm:disabled {
    background-color: #2a6ae6;
    opacity: 0.6;
    cursor: not-allowed;
}

.loading-spinner {
    border: 4px solid #f3f3f3;
    border-top: 4px solid #3a7bfd;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% {
        transform: rotate(0deg);
    }

    100% {
        transform: rotate(360deg);
    }
}

.register-form {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.register-form .password-input {
    margin-bottom: 0;
}

.email-check-message,
.password-match-error {
    font-size: 12px;
    text-align: left;
    padding: 4px 0 0 4px;
    min-height: 16px;
}

.email-check-message.valid {
    color: #2ecc71;
}

.email-check-message.invalid,
.password-match-error,
.register-error-message {
    color: #e74c3c;
}

.email-check-message.checking {
    color: #a0a0a0;
}

.register-error-message {
    font-size: 14px;
    font-weight: 500;
    min-height: 20px;
    margin-top: 16px;
    margin-bottom: -8px;
}
</style>