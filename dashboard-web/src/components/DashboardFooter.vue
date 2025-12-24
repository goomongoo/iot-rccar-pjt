<script setup>
</script>

<template>
    <footer class="dashboard-footer">
        <div class="footer-section footer-left">
            <RouterLink to="/" class="footer-icon home-icon">
                <i class="bi bi-car-front-fill"></i>
            </RouterLink>
        </div>

        <div class="footer-section footer-center">
            <button class="footer-icon"><i class="bi bi-dash-lg"></i></button>
            <div class="temperature-display">
                <i class="bi bi-thermometer-half"></i>
                <span>23°C</span>
            </div>
            <button class="footer-icon"><i class="bi bi-plus-lg"></i></button>
        </div>

        <div class="footer-section footer-right">
            <button class="footer-icon"><i class="bi bi-wind"></i></button>
            <button class="footer-icon"><i class="bi bi-vinyl-fill"></i></button>
        </div>
    </footer>
</template>

<style scoped>
.dashboard-footer {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    padding: 0 16px;
    margin-top: 12px;
    border-top: 1px solid #2c3440;
    height: 60px;
    flex-shrink: 0;
}

.footer-section {
    display: flex;
    align-items: center;
    gap: 20px;
}

.footer-center {
    gap: 24px;
}

.footer-right {
    justify-content: flex-end;
}

.footer-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    color: #a0a0a0;
    background: none;
    border: none;
    cursor: pointer;
    transition: color 0.2s ease;
    padding: 8px;
    border-radius: 50%;
    text-decoration: none;
}

.footer-icon:hover {
    color: #ffffff;
    background-color: #3a7bfd;
}

.home-icon {
    font-size: 28px;
    color: #e0e0e0;
}

.home-icon:hover {
    color: #ffffff;
    background-color: transparent;
}


.temperature-display {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 18px;
    color: #e0e0e0;
}
</style>