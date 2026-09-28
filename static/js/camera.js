const fileInput = document.getElementById("fileInput");
const submitFileInput = document.getElementById("submitFileInput");
const uploadPreview = document.getElementById("uploadPreview");
const uploadPreviewImage = document.getElementById("uploadPreviewImage");
const removeUpload = document.getElementById("removeUpload");
const dropzone = document.getElementById("dropzone");

const cameraVideo = document.getElementById("cameraVideo");
const cameraCanvas = document.getElementById("cameraCanvas");
const cameraPlaceholder = document.getElementById("cameraPlaceholder");
const cameraError = document.getElementById("cameraError");
const startCameraBtn = document.getElementById("startCameraBtn");
const captureBtn = document.getElementById("captureBtn");
const capturePreview = document.getElementById("capturePreview");
const capturePreviewImage = document.getElementById("capturePreviewImage");
const retakeActions = document.getElementById("retakeActions");
const retakeBtn = document.getElementById("retakeBtn");
const usePhotoBtn = document.getElementById("usePhotoBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const analysisForm = document.getElementById("analysisForm");
const selectedSource = document.getElementById("selectedSource");
const loadingOverlay = document.getElementById("loadingOverlay");
const heroCameraBtn = document.getElementById("heroCameraBtn");

let cameraStream = null;
let capturedBlob = null;
let selectedMode = null;

function setSelectedFile(file, source) {
    if (!file) return;

    const validTypes = ["image/jpeg", "image/png"];
    if (!validTypes.includes(file.type)) {
        alert("Please choose a JPG, JPEG, or PNG image.");
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        alert("Image is too large. Maximum size is 10 MB.");
        return;
    }

    capturedBlob = null;
    selectedMode = source;
    const objectUrl = URL.createObjectURL(file);
    uploadPreviewImage.src = objectUrl;
    uploadPreview.classList.remove("hidden");

    // Clone the file into the actual form's file input.
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    submitFileInput.files = dataTransfer.files;

    selectedSource.textContent = source === "camera"
        ? "Captured camera photo selected"
        : `Upload selected: ${file.name}`;

    analyzeBtn.disabled = false;
}

fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
        setSelectedFile(fileInput.files[0], "upload");
    }
});

removeUpload.addEventListener("click", () => {
    fileInput.value = "";
    submitFileInput.value = "";
    uploadPreview.classList.add("hidden");
    selectedSource.textContent = "No image selected";
    analyzeBtn.disabled = true;
    selectedMode = null;
});

["dragenter", "dragover"].forEach(evt => {
    dropzone.addEventListener(evt, e => {
        e.preventDefault();
        dropzone.classList.add("dragging");
    });
});
["dragleave", "drop"].forEach(evt => {
    dropzone.addEventListener(evt, e => {
        e.preventDefault();
        dropzone.classList.remove("dragging");
    });
});
dropzone.addEventListener("drop", e => {
    const file = e.dataTransfer.files[0];
    if (file) setSelectedFile(file, "upload");
});

async function startCamera() {
    cameraError.classList.add("hidden");

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        cameraError.textContent = "Your browser does not support the camera API.";
        cameraError.classList.remove("hidden");
        return;
    }

    try {
        stopCamera();

        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: "environment" },
                width: { ideal: 1280 },
                height: { ideal: 720 }
            },
            audio: false
        });

        cameraVideo.srcObject = cameraStream;
        cameraVideo.classList.add("live");
        cameraPlaceholder.classList.add("hidden");
        captureBtn.disabled = false;
        startCameraBtn.textContent = "Restart Camera";
    } catch (error) {
        let message = "Camera could not be started.";
        if (error.name === "NotAllowedError") {
            message = "Camera permission was denied. Allow camera access in your browser settings and try again.";
        } else if (error.name === "NotFoundError") {
            message = "No camera was found on this device.";
        } else if (window.isSecureContext === false) {
            message = "Camera access normally requires HTTPS (or localhost). Use http://localhost:5000 on the same device, or deploy the app with HTTPS.";
        }
        cameraError.textContent = message;
        cameraError.classList.remove("hidden");
    }
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    captureBtn.disabled = true;
}

function capturePhoto() {
    if (!cameraStream) return;

    const width = cameraVideo.videoWidth || 1280;
    const height = cameraVideo.videoHeight || 720;

    cameraCanvas.width = width;
    cameraCanvas.height = height;

    const ctx = cameraCanvas.getContext("2d");
    ctx.drawImage(cameraVideo, 0, 0, width, height);

    cameraCanvas.toBlob(blob => {
        if (!blob) return;

        capturedBlob = blob;
        capturePreviewImage.src = URL.createObjectURL(blob);
        capturePreview.classList.remove("hidden");
        retakeActions.classList.remove("hidden");

        stopCamera();
        cameraVideo.classList.remove("live");

        selectedSource.textContent = "Camera photo captured";
    }, "image/jpeg", 0.92);
}

function retakePhoto() {
    capturedBlob = null;
    capturePreview.classList.add("hidden");
    retakeActions.classList.add("hidden");
    startCamera();
}

function useCapturedPhoto() {
    if (!capturedBlob) return;

    const file = new File(
        [capturedBlob],
        `camera_capture_${Date.now()}.jpg`,
        { type: "image/jpeg" }
    );
    setSelectedFile(file, "camera");
    uploadPreviewImage.src = URL.createObjectURL(file);
}

startCameraBtn.addEventListener("click", startCamera);
captureBtn.addEventListener("click", capturePhoto);
retakeBtn.addEventListener("click", retakePhoto);
usePhotoBtn.addEventListener("click", useCapturedPhoto);

heroCameraBtn.addEventListener("click", () => {
    document.getElementById("detection").scrollIntoView({ behavior: "smooth" });
    setTimeout(startCamera, 500);
});

analysisForm.addEventListener("submit", e => {
    if (!submitFileInput.files.length) {
        e.preventDefault();
        alert("Please upload or capture an image first.");
        return;
    }
    loadingOverlay.classList.remove("hidden");

    const messages = [
        "Detecting cracks...",
        "Measuring crack dimensions...",
        "Calculating severity...",
        "Generating report..."
    ];
    let index = 0;
    setInterval(() => {
        const text = document.getElementById("loadingText");
        if (text && index < messages.length) text.textContent = messages[index++];
    }, 900);
});

window.addEventListener("beforeunload", stopCamera);
