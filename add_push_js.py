import re

path = "static/js/dashboard.js"
with open(path, "r", encoding="utf-8") as f:
    js = f.read()

push_js = """
// --- Web Push Registration (iOS Support) ---
window.urlB64ToUint8Array = function(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
};

async function enableWebPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        showToast('Web Push not supported on this browser. Try saving as PWA on iOS 16.4+', 'warning');
        return;
    }
    try {
        const registration = await navigator.serviceWorker.register('/static/sw.js');
        console.log('SW registered:', registration);
        
        let permission = await Notification.requestPermission();
        if (permission !== 'granted') {
            showToast('Permission for notifications denied', 'error');
            return;
        }

        const vapidRes = await fetch('/api/push/public_key', { headers: {'Authorization': 'Bearer '+token} });
        const vapidData = await vapidRes.json();
        const applicationServerKey = urlB64ToUint8Array(vapidData.public_key);

        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey
        });

        const subRes = await fetch('/api/push/subscribe', {
            method: 'POST',
            headers: {'Authorization': 'Bearer '+token, 'Content-Type': 'application/json'},
            body: JSON.stringify(subscription)
        });
        
        if (subRes.ok) {
            showToast('iOS Push Notifications Enabled!', 'success');
        } else {
            showToast('Failed to save push subscription', 'error');
        }
    } catch(e) {
        showToast('Error enabling push: ' + e.message, 'error');
        console.error(e);
    }
}
// ---------------------------------------------
"""

if "enableWebPushNotifications" not in js:
    js += "\n" + push_js

with open(path, "w", encoding="utf-8") as f:
    f.write(js)
