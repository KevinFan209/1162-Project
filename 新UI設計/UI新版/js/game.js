function toggleMenu() {
    document.getElementById('sideMenu').classList.toggle('open');
    document.getElementById('overlay').classList.toggle('open');
}

const multiple = 200;
const mouseOverContainer = document.getElementsByTagName("body")[0];
const element = document.getElementsByClassName("monopoly-board")[0];

function transformElement(x, y) {
  let box = element.getBoundingClientRect();
  let calcX = -(y - box.y - (box.height / 2)) / multiple + 35;
  let calcY = (x - box.x - (box.width / 2)) / multiple;
  
  element.style.transform  = "rotateX("+ calcX +"deg) "
                        + "rotateY("+ calcY +"deg)";
}

mouseOverContainer.addEventListener('mousemove', (e) => {
  window.requestAnimationFrame(function(){
    transformElement(e.clientX, e.clientY);
  });
});

mouseOverContainer.addEventListener('mouseleave', (e) => {
  window.requestAnimationFrame(function(){
    element.style.transform = "rotateX(35deg)";
  });
});