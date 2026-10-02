// Service worker for web push ("Trade Won" alerts). Registered from /static/sw.js.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
    let data = { title: "Kalshi AI Trader", body: "New alert", url: "/saas_dashboard.html" };
    if (event.data) {
        try {
            data = Object.assign(data, event.data.json());
        } catch (e) {
            data.body = event.data.text();
        }
    }
    const options = {
        body: data.body,
        icon: "/static/assets/app_icon_192.png",
        badge: "/static/assets/app_icon_192.png",
        tag: data.tag || undefined,
        vibrate: [200, 100, 200],
        data: { url: data.url || "/saas_dashboard.html" }
    };
    event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const url = (event.notification.data && event.notification.data.url) || "/saas_dashboard.html";
    event.waitUntil(
        clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
            for (const client of clientList) {
                if ("focus" in client) return client.focus();
            }
            return clients.openWindow(url);
        })
    );
});
