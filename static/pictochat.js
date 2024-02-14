const show_butt = document.getElementById("drawbutton");
const pictowindow = document.getElementById("pictochat-container");
var window_state = false;
show_butt.addEventListener("click", function() {
    if(window_state){
        pictowindow.style.height = "0px";
        window_state = false;
    }else{
        pictowindow.style.height = "170px";
        window_state = true;
    }
});

const canvas = document.getElementById("pictochat-canvas");
const ctx = canvas.getContext("2d");
var usercolor = "#f66";
canvas.style["outline-color"] = usercolor;

var colors = ["#000", usercolor];
var currentCol = 0;
ctx.strokeStyle = colors[0];
var isdraw = false;

canvas.addEventListener("pointerdown", function(event) {
    isdraw = true;
    const x = event.clientX - canvas.offsetLeft;
    const y = event.clientY - canvas.offsetTop;
    ctx.lineTo(x, y);
    ctx.stroke();
});

canvas.addEventListener("pointermove", function(event) {
    if (!isdraw) return;
    const x = event.clientX - canvas.offsetLeft;
    const y = event.clientY - canvas.offsetTop;
    ctx.lineTo(x, y);
    ctx.stroke();
});

canvas.addEventListener("pointerup", function(event) {
    isdraw = false;
    ctx.beginPath();
});

canvas.addEventListener("pointerout", function(event) {
    isdraw = false;
    ctx.beginPath();
});

const clear_butt = document.getElementById("pictochat-clear");
const send_butt = document.getElementById("pictochat-send");
const toggle_butt = document.getElementById("pictochat-togglecolor");
const penicon = document.getElementById("pictochat-pencil");
penicon.style.fill = colors[currentCol];

clear_butt.addEventListener("click", function() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
});

toggle_butt.addEventListener("click", function() {
    currentCol = (currentCol+1)%colors.length;
    ctx.strokeStyle = colors[currentCol];
    penicon.style.fill = colors[currentCol];
});

function updateColor(col){
    usercolor = col;
    colors[1] = col;
    canvas.style["outline-color"] = col;
    if(currentCol == 1){
        ctx.strokeStyle = colors[currentCol];
        penicon.style.fill = colors[currentCol];
    }
}
