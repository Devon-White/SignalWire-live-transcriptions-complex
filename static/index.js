let socket;
let callList = {};

const callListIds = document.getElementById('call-list-ids');
const confirmButton = document.getElementById('confirm-button');
const startButton = document.getElementById('start-button');
const disconnectButton = document.getElementById('disconnect-button');
const downloadButton = document.getElementById('download-button'); // Download button
const inputArea = document.getElementById('input-area');
const transcriptDiv = document.getElementById('transcript');
const statusDiv = document.getElementById('status');
const errorBanner = document.getElementById('error-banner');
const errorMessage = document.getElementById('error-message');
const disconnectCallButton = document.getElementById('disconnect-call-button');

let selectedCall = null; // Keep track of the selected item

// Confirm button is disabled by default
confirmButton.disabled = true;

// Download button is hidden by default
downloadButton.style.display = 'none'; // Hide download button by default

// Use event delegation to handle clicks on call list items
callListIds.onclick = function(event) {
    let target = event.target.closest('LI');
    if (!target || target.classList.contains('active')) return;
    if (!target) return;

    if (selectedCall === target) {
        selectedCall.classList.remove('selected');
        confirmButton.disabled = true;
        selectedCall = null;
        return;
    }

    if (selectedCall) {
        selectedCall.classList.remove('selected');
    }
    selectedCall = target;
    selectedCall.classList.add('selected');
    selectedCall.classList.remove('call-list-item-hover');
    confirmButton.disabled = false;
};

callListIds.onmouseover = function(event) {
    let target = event.target.closest('LI');
    if (!target) return;

    if (!target.classList.contains('selected') && !target.classList.contains('active')) {
        target.classList.add('call-list-item-hover');
    }
};

callListIds.onmousedown = function() {
    return false;
};

callListIds.onmouseout = function(event) {
    let target = event.target.closest('LI');
    if (!target) return;

    target.classList.remove('call-list-item-hover');
};

function update_call_activity(currentIds, activeSid) {
    currentIds.forEach(id => {
        let callItem = document.getElementById(id);
        if (id === activeSid) {
            callItem.classList.add('active');
        } else {
            callItem.classList.remove('active');
        }
    });
}

function startWebSocket() {
    socket = new WebSocket(`wss://${location.host}/listen`);
    console.log('startWebSocket()', socket)

    socket.onopen = () => {
        startButton.style.display = 'none';
        disconnectButton.style.display = 'block';
    };

    socket.onclose = () => {
        callList = {};
        selectedCall = null;
        confirmButton.disabled = true;
        callListIds.innerHTML = '';
        disconnectButton.style.display = 'none';
        startButton.style.display = 'block';
        if (inputArea) inputArea.style.display = 'none';
    };

    socket.onmessage = event => {
        const data = JSON.parse(event.data);

        switch (true) {
            case 'duplicate' in data:
                if (errorBanner.style.display === 'block') {
                    break;
                } else {
                    errorMessage.innerText = `Error: Already listening to call ${data.duplicate}.`;
                    errorBanner.style.transform = 'translateY(-100%)';
                    errorBanner.style.display = 'block';
                    setTimeout(function() {
                        errorBanner.style.transform = 'translateY(0)';
                    }, 100);
                    setTimeout(function() {
                        errorBanner.style.transform = 'translateY(-100%)';
                        setTimeout(function() {
                            errorBanner.style.display = 'none';
                            errorBanner.style.transform = 'translateY(0)';
                        }, 500);
                    }, 5000);
                    break;
                }

            case data.action === 'history':
                // Clear any existing transcripts
                transcriptDiv.innerHTML = '';

                // Loop through each transcript in the history
                data.history.forEach(transcript => {
                    try {
                        // Create a new div for the transcript
                        let messageDiv = document.createElement('div');
                        messageDiv.className = `message ${transcript.speaker === 'caller' ? 'caller' : 'callee'}`;
                        messageDiv.innerText = transcript.transcript;
                        console.log(messageDiv)

                        // Append the transcript div to the transcript container
                        console.log(transcriptDiv.innerHTML)
                        transcriptDiv.appendChild(messageDiv);
                        console.log(transcriptDiv.innerHTML)
                    } catch (error) {
                        console.error(error);
                    }
                });

                break;

            case data.action === 'transcript_message':
                console.log(event);
                let speaker = data.transcript.speaker;
                let trans = data.transcript.transcript;
                let messageDiv = document.createElement('div');
                messageDiv.className = `message ${speaker === 'caller' ? 'caller' : 'callee'}`;
                messageDiv.innerHTML = trans;
                transcriptDiv.appendChild(messageDiv);
                break;


            case data.action === 'input':
                statusDiv.innerText = `Connected to call: ${data.sid}`;
                transcriptDiv.innerHTML = '';
                document.getElementById('disconnect-call-button').style.display = 'block';
                downloadButton.disabled = false;
                downloadButton.style.display = 'block'; // Show download button

                const currentIds = Object.keys(callList).filter(id => callList[id]);

                update_call_activity(currentIds, data.sid) // Add this line back

                break;


            case data.status:
                statusDiv.innerHTML += data.status + '<br/>';
                break;
            case data.action === 'update_call_list':
                console.log(event);
                const newDataCallList = data['callList'];
                const removedIds = Object.keys(callList).filter(id => !newDataCallList.includes(id));
                removedIds.forEach(id => {
                    if (selectedCall && selectedCall.innerText === id) { // Check if the selected call has ended
                        disconnectCallButton.style.display = 'none';
                    }
                    delete callList[id];
                    const liList = callListIds.getElementsByTagName('li');
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
                        li.innerHTML = id;
                        li.id = id;
                        callListIds.appendChild(li);
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
        console.log(selectedCall.innerHTML);
        socket.send(JSON.stringify({
            'action': 'input',
            'call_sid': selectedCall.innerHTML
        }));
        selectedCall.classList.remove('selected');
        confirmButton.disabled = true;
    }
}

function disconnect() {
    if (selectedCall) {
        socket.send(JSON.stringify({
            'action': 'close',
            'call_sid': selectedCall.innerText
        }));
        selectedCall.classList.remove('selected');
        selectedCall = null;
        confirmButton.disabled = true;
    }
    socket.close();
    disconnectButton.style.display = 'none';
    startButton.style.display = 'block';
    if (inputArea) inputArea.style.display = 'none';
}

function disconnectCall() {
    if (selectedCall) {
        socket.send(JSON.stringify({
            'action': 'close',
            'call_sid': selectedCall.innerText
        }));
        selectedCall.classList.remove('selected', 'active');
        transcriptDiv.innerHTML = '';
        selectedCall = null;
        disconnectCallButton.disabled = true;
        downloadButton.disabled = true
        disconnectCallButton.style.display = 'none'
        downloadButton.style.display = 'none'
    }
}

downloadButton.onclick = function() {
    if (selectedCall) {
        const url = `/download/${selectedCall.innerText}`;
        fetch(url)
            .then(resp => resp.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `${selectedCall.innerText}.csv`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            })
            .catch(() => alert('Download failed'));
    }
};

setInterval(() => {
    disconnectCallButton.disabled = (selectedCall === null);
}, 1000);
