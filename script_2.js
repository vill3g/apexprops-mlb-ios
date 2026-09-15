
    (function() {
      let currentMtime = null;
      setInterval(async () => {
        try {
          const res = await fetch('/api/ui_version?t=' + Date.now(), { cache: 'no-store' });
          if (res.ok) {
            const data = await res.json();
            if (currentMtime === null) {
              currentMtime = data.mtime;
            } else if (data.mtime && data.mtime !== currentMtime) {
              console.log('[AutoReload] New UI version detected, reloading page...');
              window.location.reload();
            }
          }
        } catch (e) {}
      }, 1500);
    })();
  