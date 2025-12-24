<script setup>
import { ref, watch, computed } from 'vue';
import { useSystemStore } from '@/stores/systemStore';
import { db } from '@/firebase-init';
import { getStorage, ref as storageRef, uploadBytes, getDownloadURL } from "firebase/storage";
import { getAuth, EmailAuthProvider, reauthenticateWithCredential, updatePassword } from "firebase/auth";
import { collection, doc, getDocs, updateDoc, query, where } from "firebase/firestore";

const systemStore = useSystemStore();
const auth = getAuth();
const storage = getStorage();

// UI 상태 관리
const isSsafyAdmin = computed(() => systemStore.currentUser?.username === 'SSAFY');
const activeTab = ref(isSsafyAdmin.value ? 'users' : 'profile');
const isLoading = ref(false);
const modal = ref({
    isVisible: false,
    message: ''
});

// 개인정보 수정 관련 상태
const isAuthenticated = ref(false);
const passwordCheck = ref('');
const profileData = ref({
    username: systemStore.currentUser.username,
    newPassword: '',
    confirmPassword: ''
});
const profileImageFile = ref(null);
const bgImageFile = ref(null);

// 회원 관리 관련 상태
const userList = ref([]);

// 현재 로그인한 사용자의 isAdmin 여부
const isAdmin = computed(() => systemStore.currentUser?.isAdmin);

// 개인정보 수정 폼의 비밀번호 일치 여부
const passwordsMatch = computed(() => {
    if (!profileData.value.newPassword) return true;
    return profileData.value.newPassword === profileData.value.confirmPassword;
});

// 함수 선언 부
const resetProfileEditState = () => {
    isAuthenticated.value = false;
    passwordCheck.value = '';
    profileData.value = {
        username: systemStore.currentUser.username,
        newPassword: '',
        confirmPassword: ''
    };
    profileImageFile.value = null;
    bgImageFile.value = null;
    const profileInput = document.getElementById('profile-upload');
    if (profileInput) profileInput.value = '';
    const bgInput = document.getElementById('bg-upload');
    if (bgInput) bgInput.value = '';
};

const verifyPassword = async () => {
    if (!passwordCheck.value) {
        alert('비밀번호를 입력하세요.');
        return;
    }
    isLoading.value = true;
    try {
        const credential = EmailAuthProvider.credential(auth.currentUser.email, passwordCheck.value);
        await reauthenticateWithCredential(auth.currentUser, credential);
        isAuthenticated.value = true;
    } catch (error) {
        alert('비밀번호가 올바르지 않습니다.');
    } finally {
        isLoading.value = false;
    }
};

const uploadFile = async (file, path) => {
    const fileRef = storageRef(storage, path);
    await uploadBytes(fileRef, file);
    return await getDownloadURL(fileRef);
};

const updateProfile = async () => {
    if (profileData.value.newPassword && !passwordsMatch.value) {
        alert('새 비밀번호가 일치하지 않습니다.');
        return;
    }
    isLoading.value = true;
    try {
        const user = auth.currentUser;
        const userDocRef = doc(db, 'users', user.uid);
        const updateData = { username: profileData.value.username };

        if (profileImageFile.value) {
            updateData.profileUrl = await uploadFile(profileImageFile.value, `profiles/${user.uid}/${profileImageFile.value.name}`);
        }
        if (bgImageFile.value) {
            updateData.bgUrl = await uploadFile(bgImageFile.value, `backgrounds/${user.uid}/${bgImageFile.value.name}`);
        }

        await updateDoc(userDocRef, updateData);

        if (profileData.value.newPassword) {
            await updatePassword(user, profileData.value.newPassword);
        }

        systemStore.setCurrentUser({ ...systemStore.currentUser, ...updateData });
        modal.value = { isVisible: true, message: '회원 정보 변경에 성공했습니다.' };
    } catch (error) {
        alert('정보 변경에 실패했습니다.');
    } finally {
        isLoading.value = false;
    }
};

const fetchUsers = async () => {
    isLoading.value = true;
    try {
        const q = query(collection(db, "users"), where("useremail", "!=", "admin@ssafy.com"));
        const querySnapshot = await getDocs(q);
        userList.value = querySnapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    } catch (error) {
        console.error("Error fetching users:", error);
    } finally {
        isLoading.value = false;
    }
};

const toggleAdminStatus = async (user) => {
    try {
        const userDocRef = doc(db, 'users', user.id);
        const newAdminStatus = !user.isAdmin;
        await updateDoc(userDocRef, { isAdmin: newAdminStatus });
        user.isAdmin = newAdminStatus;
    } catch (error) {
        alert('권한 변경에 실패했습니다.');
    }
};

const handleFileChange = (event, type) => {
    const file = event.target.files[0];
    if (file) {
        if (type === 'profile') profileImageFile.value = file;
        if (type === 'bg') bgImageFile.value = file;
    }
};

const closeModal = () => {
    modal.value.isVisible = false;
    resetProfileEditState();
};

// Watch 로직
watch(activeTab, (newTab) => {
    if (newTab === 'users' && isAdmin.value) {
        fetchUsers();
    }
    if (newTab === 'profile') {
        resetProfileEditState();
    }
}, { immediate: true });
</script>

<template>
    <div class="settings-container">
        <nav class="settings-nav">
            <ul>
                <li v-if="!isSsafyAdmin" :class="{ active: activeTab === 'profile' }" @click="activeTab = 'profile'">
                    <i class="bi bi-person-fill"></i> 개인정보 수정
                </li>
                <li v-if="isAdmin" :class="{ active: activeTab === 'users' }" @click="activeTab = 'users'">
                    <i class="bi bi-people-fill"></i> 회원 관리
                </li>
            </ul>
        </nav>

        <section class="settings-content">
            <div v-if="activeTab === 'profile'">
                <div v-if="!isAuthenticated" class="auth-gate">
                    <h3>비밀번호 확인</h3>
                    <p>개인정보를 안전하게 보호하기 위해 비밀번호를 다시 한번 입력해주세요.</p>
                    <input type="password" v-model="passwordCheck" placeholder="비밀번호 입력"
                        @keyup.enter="verifyPassword" />
                    <button @click="verifyPassword" :disabled="isLoading">
                        {{ isLoading ? '확인 중...' : '확인' }}
                    </button>
                </div>
                <div v-else class="profile-editor">
                    <h3>개인정보 수정</h3>
                    <div class="form-group">
                        <label>프로필 사진</label>
                        <input id="profile-upload" type="file" accept="image/*"
                            @change="handleFileChange($event, 'profile')">
                    </div>
                    <div class="form-group">
                        <label>이름</label>
                        <input type="text" v-model="profileData.username">
                    </div>
                    <div class="form-group">
                        <label>새 비밀번호</label>
                        <input type="password" v-model="profileData.newPassword" placeholder="변경할 경우에만 입력">
                    </div>
                    <div class="form-group">
                        <label>새 비밀번호 확인</label>
                        <input type="password" v-model="profileData.confirmPassword" placeholder="비밀번호 다시 입력">
                        <p v-if="!passwordsMatch" class="error-text">비밀번호가 일치하지 않습니다.</p>
                    </div>
                    <div class="form-group">
                        <label>배경 화면</label>
                        <input id="bg-upload" type="file" accept="image/*" @change="handleFileChange($event, 'bg')">
                    </div>
                    <button @click="updateProfile" :disabled="isLoading || !passwordsMatch">
                        {{ isLoading ? '저장 중...' : '저장' }}
                    </button>
                </div>
            </div>

            <div v-if="activeTab === 'users' && isAdmin" class="user-management">
                <h3>회원 관리</h3>
                <div v-if="isLoading" class="loading-text">회원 목록을 불러오는 중...</div>
                <ul v-else class="user-list">
                    <li v-for="user in userList" :key="user.id" class="user-item">
                        <div class="user-info">
                            <span class="username">{{ user.username }}</span>
                            <span class="useremail">{{ user.useremail }}</span>
                        </div>
                        <div class="admin-toggle">
                            <span>관리자 권한</span>
                            <label class="switch">
                                <input type="checkbox" :checked="user.isAdmin"
                                    :disabled="auth.currentUser && user.id === auth.currentUser.uid"
                                    @change="toggleAdminStatus(user)">
                                <span class="slider round"></span>
                            </label>
                        </div>
                    </li>
                </ul>
            </div>
        </section>

        <div v-if="modal.isVisible" class="modal-overlay">
            <div class="modal-content">
                <h2>알림</h2>
                <p>{{ modal.message }}</p>
                <button @click="closeModal" class="btn-confirm">확인</button>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* 기본 레이아웃 */
.settings-container {
    display: flex;
    height: 100%;
    gap: 24px;
}

.settings-nav {
    flex-basis: 25%;
    background-color: #2c3440;
    border-radius: 12px;
    padding: 16px;
}

.settings-content {
    flex-basis: 75%;
    background-color: #2c3440;
    border-radius: 12px;
    padding: 32px;
    overflow-y: auto;
}

/* 왼쪽 네비게이션 */
.settings-nav ul {
    list-style: none;
    padding: 0;
    margin: 0;
}

.settings-nav li {
    padding: 16px;
    border-radius: 8px;
    cursor: pointer;
    transition: background-color 0.2s;
    font-size: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
}

.settings-nav li:hover {
    background-color: #3e4c5a;
}

.settings-nav li.active {
    background-color: #3a7bfd;
    color: white;
    font-weight: 500;
}

/* 오른쪽 컨텐츠 공통 */
h3 {
    margin-top: 0;
    margin-bottom: 24px;
    font-size: 22px;
    border-bottom: 1px solid #3e4c5a;
    padding-bottom: 16px;
}

button {
    padding: 10px 20px;
    border-radius: 6px;
    border: none;
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    background-color: #3a7bfd;
    color: white;
    transition: background-color 0.2s;
}

button:disabled {
    background-color: #555;
    cursor: not-allowed;
}

/* 개인정보 수정: 비밀번호 확인 */
.auth-gate {
    max-width: 400px;
    margin: 40px auto;
    text-align: center;
}

.auth-gate p {
    color: #a0a0a0;
    margin-bottom: 24px;
}

.auth-gate input {
    width: 100%;
    padding: 12px;
    border-radius: 6px;
    border: 1px solid #3e4c5a;
    background-color: #1a2027;
    color: #e0e0e0;
    font-size: 16px;
    margin-bottom: 16px;
}

/* 개인정보 수정: 에디터 */
.profile-editor .form-group {
    margin-bottom: 20px;
}

.profile-editor label {
    display: block;
    margin-bottom: 8px;
    color: #a0a0a0;
}

.profile-editor input[type="text"],
.profile-editor input[type="password"] {
    width: 50%;
    padding: 10px;
    border-radius: 6px;
    border: 1px solid #3e4c5a;
    background-color: #1a2027;
    color: #e0e0e0;
}

.error-text {
    color: #e74c3c;
    font-size: 12px;
    margin-top: 6px;
}

/* 회원 관리 */
.user-list {
    list-style: none;
    padding: 0;
    margin: 0;
}

.user-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 8px;
    border-bottom: 1px solid #3e4c5a;
}

.user-item:last-child {
    border-bottom: none;
}

.user-info {
    display: flex;
    flex-direction: column;
}

.user-info .username {
    font-weight: 500;
}

.user-info .useremail {
    font-size: 14px;
    color: #a0a0a0;
}

.admin-toggle {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #a0a0a0;
}

/* 토글 스위치 */
.switch {
    position: relative;
    display: inline-block;
    width: 50px;
    height: 28px;
}

.switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.slider {
    position: absolute;
    cursor: pointer;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: #555e68;
    transition: .4s;
}

.slider:before {
    position: absolute;
    content: "";
    height: 20px;
    width: 20px;
    left: 4px;
    bottom: 4px;
    background-color: white;
    transition: .4s;
}

input:checked+.slider {
    background-color: #3a7bfd;
}

input:disabled+.slider {
    cursor: not-allowed;
    background-color: #3e4c5a;
}

input:checked+.slider:before {
    transform: translateX(22px);
}

.slider.round {
    border-radius: 28px;
}

.slider.round:before {
    border-radius: 50%;
}

/* 모달 */
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

.modal-content p {
    color: #e0e0e0;
    margin-bottom: 24px;
}

.btn-confirm {
    min-width: 100px;
}
</style>