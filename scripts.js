document.addEventListener("DOMContentLoaded", function () {
    const fileActions = document.getElementById("file-actions");

    // Check if fileActions exists (meaning user is logged in)
    if (fileActions) {
        fileActions.style.display = "block"; // Show Upload/Download buttons if logged in
    }
});
