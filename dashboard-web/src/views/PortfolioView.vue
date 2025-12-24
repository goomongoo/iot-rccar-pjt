<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { useSystemStore } from '@/stores/systemStore.js';

const systemStore = useSystemStore();
const scrollContainer = ref(null);

const scrollToSection = (id) => {
    const section = document.getElementById(id);
    if (section) {
        section.scrollIntoView({ behavior: 'smooth' });
    }
};

const currentSlide = ref(0);
const mainImages = [
    "https://placehold.co/800x400/3a7bfd/ffffff?text=Project+A",
    "https://placehold.co/800x400/2ecc71/ffffff?text=Project+B",
    "https://placehold.co/800x400/e74c3c/ffffff?text=Project+C",
];
let slideInterval = null;

const skills = ref([
    { name: 'Vue.js', level: 90 },
    { name: 'JavaScript', level: 85 },
    { name: 'HTML & CSS', level: 95 },
    { name: 'Node.js', level: 75 },
]);
const skillSection = ref(null);
const skillsVisible = ref(false);
let observer = null;

onMounted(() => {
    slideInterval = setInterval(() => {
        currentSlide.value = (currentSlide.value + 1) % mainImages.length;
    }, 3000);

    observer = new IntersectionObserver(
        (entries) => {
            if (entries[0].isIntersecting) {
                skillsVisible.value = true;
                observer.disconnect();
            }
        },
        { threshold: 0.5 }
    );
    if (skillSection.value) {
        observer.observe(skillSection.value);
    }
});

onBeforeUnmount(() => {
    clearInterval(slideInterval);
    if (observer) {
        observer.disconnect();
    }
});
</script>

<template>
    <div class="portfolio-container" ref="scrollContainer">
        <nav class="portfolio-nav">
            <div class="nav-brand">{{ systemStore.currentUser.username }}'s Portfolio</div>
            <div class="nav-links">
                <a @click="scrollToSection('main')">Main</a>
                <a @click="scrollToSection('about')">About</a>
                <a @click="scrollToSection('skill')">Skill</a>
                <a @click="scrollToSection('stack')">Stack</a>
                <a @click="scrollToSection('closing')">Closing</a>
            </div>
        </nav>

        <div class="portfolio-content">
            <section id="main" class="portfolio-section main-section">
                <div class="slider">
                    <div class="slides" :style="{ transform: `translateX(-${currentSlide * 100}%)` }">
                        <div class="slide" v-for="image in mainImages" :key="image">
                            <img :src="image" alt="Portfolio Image">
                        </div>
                    </div>
                </div>
            </section>

            <section id="about" class="portfolio-section">
                <h2>About Me</h2>
                <div class="about-card">
                    <img src="https://placehold.co/150x150/3a7bfd/ffffff?text=Profile" alt="Profile Picture"
                        class="profile-pic">
                    <div class="about-text">
                        <h3>열정적인 개발자 {{ systemStore.userName }}입니다.</h3>
                        <p>사용자 경험을 최우선으로 생각하며, 직관적이고 효율적인 웹 애플리케이션을 만드는 것을 목표로 합니다. 새로운 기술을 배우고 동료들과 지식을 공유하는 것을 즐깁니다.
                        </p>
                        <ul class="contact-list">
                            <li><i class="bi bi-envelope-fill"></i> annyeong@kimsunsu.dev</li>
                            <li><i class="bi bi-telephone-fill"></i> 010-1234-5678</li>
                            <li><i class="bi bi-github"></i> github.com/kimsunsu</li>
                        </ul>
                    </div>
                </div>
            </section>

            <section id="skill" class="portfolio-section" ref="skillSection">
                <h2>My Skills</h2>
                <div class="skill-grid">
                    <div class="skill-item" v-for="skill in skills" :key="skill.name">
                        <p>{{ skill.name }}</p>
                        <div class="progress-bar">
                            <div class="progress" :style="{ width: skillsVisible ? skill.level + '%' : '0%' }"></div>
                        </div>
                    </div>
                </div>
            </section>

            <section id="stack" class="portfolio-section">
                <h2>My Tech Stack</h2>
                <table class="stack-table">
                    <thead>
                        <tr>
                            <th>Category</th>
                            <th>Technologies</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Frontend</td>
                            <td>Vue.js, React, JavaScript (ES6+), HTML5, CSS3</td>
                        </tr>
                        <tr>
                            <td>Backend</td>
                            <td>Node.js, Express, Python, Django</td>
                        </tr>
                        <tr>
                            <td>Database</td>
                            <td>MySQL, MongoDB, Firebase</td>
                        </tr>
                        <tr>
                            <td>DevOps</td>
                            <td>Docker, Git, AWS (EC2, S3)</td>
                        </tr>
                    </tbody>
                </table>
            </section>

            <section id="closing" class="portfolio-section">
                <div class="closing-card">
                    <img src="https://placehold.co/600x300/255f4c/ffffff?text=Thank+You" alt="Closing Image">
                    <div class="closing-text">
                        <h2>감사합니다!</h2>
                        <p>언제나 긍정적인 자세로 함께 성장할 기회를 기다리고 있습니다. 편하게 연락 주세요!</p>
                    </div>
                </div>
            </section>
        </div>
    </div>
</template>

<style scoped>
.portfolio-container {
    height: 100%;
    overflow-y: scroll;
    scroll-behavior: smooth;
    color: #e0e0e0;

    &::-webkit-scrollbar {
        display: none;
    }

    scrollbar-width: none;
}

.portfolio-nav {
    position: sticky;
    top: 0;
    left: 0;
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 32px;
    background-color: rgba(26, 32, 39, 0.8);
    backdrop-filter: blur(10px);
    z-index: 10;
    border-bottom: 1px solid #2c3440;
    box-sizing: border-box;
}

.nav-brand {
    font-size: 19px;
    font-weight: bold;
}

.nav-links a {
    margin-left: 24px;
    cursor: pointer;
    transition: color 0.2s;
}

.nav-links a:hover {
    color: #3a7bfd;
}

.portfolio-content {
    padding: 0 32px;
}

.portfolio-section {
    padding: 64px 0;
    border-bottom: 1px solid #2c3440;
}

.portfolio-section:last-child {
    border-bottom: none;
}

h2 {
    font-size: 32px;
    margin-bottom: 32px;
    text-align: center;
}

.slider {
    width: 100%;
    overflow: hidden;
    border-radius: 12px;
}

.slides {
    display: flex;
    transition: transform 0.5s ease-in-out;
}

.slide {
    min-width: 100%;
}

.slide img {
    width: 100%;
    display: block;
}

.about-card {
    display: flex;
    align-items: center;
    gap: 32px;
    background-color: #2c3440;
    padding: 32px;
    border-radius: 12px;
}

.profile-pic {
    width: 150px;
    height: 150px;
    border-radius: 50%;
    object-fit: cover;
}

.about-text {
    flex: 1;
}

.contact-list {
    list-style: none;
    padding: 0;
    margin-top: 16px;
}

.contact-list li {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}

/* Skill 섹션 */
.skill-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 32px;
}

.skill-item p {
    margin-bottom: 8px;
}

.progress-bar {
    background-color: #2c3440;
    border-radius: 5px;
    height: 20px;
    overflow: hidden;
}

.progress {
    background-color: #3a7bfd;
    height: 100%;
    border-radius: 5px;
    transition: width 1.5s ease-in-out;
}

.stack-table {
    width: 100%;
    border-collapse: collapse;
    background-color: #2c3440;
    border-radius: 12px;
    overflow: hidden;
}

.stack-table th,
.stack-table td {
    padding: 16px;
    text-align: left;
    border-bottom: 1px solid #1a2027;
}

.stack-table thead {
    background-color: #1a2027;
}

.stack-table tbody tr:last-child td {
    border-bottom: none;
}

.closing-card {
    background-color: #2c3440;
    border-radius: 12px;
    overflow: hidden;
    text-align: center;
}

.closing-card img {
    width: 100%;
    display: block;
}

.closing-text {
    padding: 32px;
}
</style>
