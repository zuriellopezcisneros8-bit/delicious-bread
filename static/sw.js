self.addEventListener('push', function(event) {
    let data = {};
    if (event.data) {
        data = event.data.json();
    }

    const title = data.title || 'Delicious Bread';
    const options = {
        body: data.body || 'Tienes una actualización sobre tu pedido.',
        icon: '/static/icon.png', // Asegúrate de tener este icono en tu carpeta static
        badge: '/static/icon2.png',
        vibrate: [200, 100, 200, 100],
        data: {
            url: '/' // A donde irá el usuario al hacer clic
        }
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});