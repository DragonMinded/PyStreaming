const show_butt = document.getElementById("drawbutton");
const clear_butt = document.getElementById("pictochat-clear");
const send_butt = document.getElementById("pictochat-send");
const toggle_butt = document.getElementById("pictochat-togglecolor");
const penicon = document.getElementById("pictochat-pencil");
const pictowindow = document.getElementById("pictochat-container");

var window_state = false;
show_butt.addEventListener("click", function() {
    if(window_state){
        pictowindow.style.height = "0px";
        window_state = false;
        $(show_butt).text("Draw");
    }else{
        pictowindow.style.height = "170px";
        window_state = true;
        $(show_butt).text("Undraw");
    }
});

const canvas = document.getElementById("pictochat-canvas");
const ctx = canvas.getContext("2d");
var usercolor = "#f66";
var colors = ["#000", usercolor];
var currentCol = 0;
ctx.strokeStyle = colors[0];
var isdraw = false;

canvas.addEventListener("pointerdown", function(event) {
    isdraw = true;
    var rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    ctx.moveTo(x-1, y-1);
    ctx.lineTo(x, y);
    ctx.stroke();
});

canvas.addEventListener("pointermove", function(event) {
    if (!isdraw) return;
    var rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    ctx.lineTo(x, y);
    ctx.stroke();
    $(send_butt).prop("disabled", false);
});

canvas.addEventListener("pointerup", function(event) {
    isdraw = false;
    ctx.beginPath();
});

canvas.addEventListener("pointerout", function(event) {
    isdraw = false;
    ctx.beginPath();
});

penicon.style.fill = colors[currentCol];

clear_butt.addEventListener("click", function() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    $(send_butt).prop("disabled", true);
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
