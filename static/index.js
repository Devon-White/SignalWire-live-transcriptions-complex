// Cache DOM elements for better performance
const domElements = {
    callListIds: document.getElementById('call-list-ids'),
    confirmButton: document.getElementById('confirm-button'),
    startButton: document.getElementById('start-button'),
    disconnectButton: document.getElementById('disconnect-button'),
    downloadButton: document.getElementById('download-button'), // Download button
    inputArea: document.getElementById('input-area'),
    transcriptDiv: document.getElementById('transcript'),
    statusDiv: document.getElementById('status'),
    errorBanner: document.getElementById('error-banner'),
    errorMessage: document.getElementById('error-message'),
    disconnectCallButton: document.getElementById('disconnect-call-button'),
};

let callList = {};
let selectedCall = null; // Keep track of the selected item
let socket;

// Confirm button is disabled by default
domElements.confirmButton.disabled = true;

// Download button is hidden by default
domElements.downloadButton.style.display = 'none'; // Hide download button by default

// Add listeners for mouseover and mouseout
domElements.callListIds.addEventListener('mouseover', handleMouseOver);
domElements.callListIds.addEventListener('mouseout', handleMouseOut);

// Use event delegation to handle clicks on call list items
domElements.callListIds.addEventListener('click', handleClick);

// Handle Mouseover event
function handleMouseOver(event) {
    let target = event.target.closest('LI');
    if (!target) return;
    if (!target.classList.contains('selected') && !target.classList.contains('active')) {
        target.classList.add('call-list-item-hover');
    }
}

// Handle Mouseout event
function handleMouseOut(event) {
    let target = event.target.closest('LI');
    if (!target) return;
    target.classList.remove('call-list-item-hover');
}

// Handle Click event
function handleClick(event) {
    let target = event.target.closest('LI');
    if (!target || target.classList.contains('active')) return;
    if (selectedCall === target) {
        selectedCall.classList.remove('selected');
        domElements.confirmButton.disabled = true;
        selectedCall = null;
        return;
    }
    if (selectedCall) {
        selectedCall.classList.remove('selected');
    }
    selectedCall = target;
    selectedCall.classList.add('selected');
    selectedCall.classList.remove('call-list-item-hover');
    domElements.confirmButton.disabled = false;
}

// Add listeners for mousedown
domElements.callListIds.addEventListener('mousedown', () => false);

async function update_call_activity(currentIds, activeSid) {
    currentIds.forEach(id => {
        let callItem = document.getElementById(id);
        if (id === activeSid) {
            callItem.classList.add('active');
        } else {
            callItem.classList.remove('active');
        }
    });
}

async function startWebSocket() {
    socket = new WebSocket(`wss://${location.host}/listen`);

    socket.onopen = () => {
        domElements.startButton.style.display = 'none';
        domElements.disconnectButton.style.display = 'block';
    };

    socket.onclose = () => {
        callList = {};
        selectedCall = null;
        domElements.confirmButton.disabled = true;
        domElements.callListIds.textContent = '';
        domElements.disconnectButton.style.display = 'none';
        domElements.startButton.style.display = 'block';
        if (domElements.inputArea) domElements.inputArea.style.display = 'none';
    };

    socket.onmessage = async (event) => {
        const data = JSON.parse(event.data);

        switch (true) {
            case 'duplicate' in data:
                if (domElements.errorBanner.style.display === 'block') {
                    break;
                } else {
                    domElements.errorMessage.textContent = `Error: Already listening to call ${data.duplicate}.`;
                    showErrorBanner();
                    break;
                }

            case data.action === 'transcript_message':
                let speaker = data.transcript.speaker;
                let trans = data.transcript.transcript;
                let messageDiv = document.createElement('div');
                messageDiv.className = `message ${speaker === 'caller' ? 'caller' : 'callee'}`;
                messageDiv.textContent = trans;
                domElements.transcriptDiv.appendChild(messageDiv);
                break;

            case data.action === 'input':
                domElements.statusDiv.textContent = `Connected to call: ${data.sid}`;
                domElements.disconnectCallButton.style.display = 'block';
                domElements.downloadButton.disabled = false;
                domElements.downloadButton.style.display = 'block'; // Show download button
                const currentIds = Object.keys(callList).filter(id => callList[id]);
                await update_call_activity(currentIds, data.sid) // Add this line back

                // Clear any existing transcripts if no history is present
                if (!data.history || data.history.length === 0) {
                    domElements.transcriptDiv.textContent = '';
                }

                // Loop through each transcript in the history
                data.history.forEach(transcript => {
                    try {
                        // Create a new div for the transcript
                        let messageDiv = document.createElement('div');
                        messageDiv.className = `message ${transcript.speaker === 'caller' ? 'caller' : 'callee'}`;
                        messageDiv.textContent = transcript.transcript;

                        // Append the transcript div to the transcript container
                        domElements.transcriptDiv.appendChild(messageDiv);
                    } catch (error) {
                        console.error(error);
                    }
                });
                break;

            case data.status:
                domElements.statusDiv.textContent += `${data.status}\n`;
                break;

            case data.action === 'update_call_list':
                const newDataCallList = data['callList'];
                const removedIds = Object.keys(callList).filter(id => !newDataCallList.includes(id));
                removedIds.forEach(id => {
                    if (selectedCall && selectedCall.textContent === id) { // Check if the selected call has ended
                        domElements.disconnectCallButton.style.display = 'none';
                    }
                    delete callList[id];
                    const liList = domElements.callListIds.getElementsByTagName('li');
                    for (let i = 0; i < liList.length; i++) {
                        if (liList[i].textContent.includes(id)) {
                            liList[i].remove();
                            break;
                        }
                    }
                });

                newDataCallList.forEach(id => {
                    if (!callList[id]) {
                        callList[id] = true;
                        const li = document.createElement('li');
                        li.textContent = id;
                        li.id = id;
                        domElements.callListIds.appendChild(li);
                    }
                });
                break;

            default:
                break;
        }
    };
}

function sendInput() {
    if (selectedCall) {
        socket.send(JSON.stringify({
            'action': 'input',
            'call_sid': selectedCall.textContent
        }));
        selectedCall.classList.remove('selected');
        domElements.confirmButton.disabled = true;
    }
}

function disconnect() {
    if (selectedCall) {
        socket.send(JSON.stringify({
            'action': 'close',
            'call_sid': selectedCall.textContent
        }));
        selectedCall.classList.remove('selected');
        selectedCall = null;
        domElements.confirmButton.disabled = true;
    }
    socket.close();
    domElements.disconnectButton.style.display = 'none';
    domElements.startButton.style.display = 'block';
    if (domElements.inputArea) domElements.inputArea.style.display = 'none';
}

function disconnectCall() {
    if (selectedCall) {
        socket.send(JSON.stringify({
            'action': 'close',
            'call_sid': selectedCall.textContent
        }));
        selectedCall.classList.remove('selected', 'active');
        domElements.transcriptDiv.textContent = '';
        selectedCall = null;
        domElements.disconnectCallButton.disabled = true;
        domElements.downloadButton.disabled = true;
        domElements.disconnectCallButton.style.display = 'none';
        domElements.downloadButton.style.display = 'none';
    }
}

domElements.downloadButton.addEventListener('click', async function() {
    if (selectedCall) {
        const url = `/download/${selectedCall.textContent}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok) {
                throw new Error(`HTTP error! status: ${resp.status}`);
            } else {
                const blob = await resp.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `${selectedCall.textContent}.csv`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            }
        } catch (error) {
            alert('Download failed');
        }
    }
});


setInterval(() => {
    domElements.disconnectCallButton.disabled = (selectedCall === null);
}, 1000);
