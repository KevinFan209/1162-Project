document.addEventListener('DOMContentLoaded', () => {
    const cylinderContainer = document.querySelector('.cylinder-container');
    const playButton = document.getElementById('play-button');
    const pauseButton = document.getElementById('pause-button');

    if (!cylinderContainer) {
        return;
    }

    playButton?.addEventListener('click', () => {
        cylinderContainer.style.animationPlayState = 'running';
    });

    pauseButton?.addEventListener('click', () => {
        cylinderContainer.style.animationPlayState = 'paused';
    });
});
