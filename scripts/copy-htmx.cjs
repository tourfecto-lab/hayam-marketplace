const fs = require('node:fs');
fs.mkdirSync('static/vendor', { recursive: true });
fs.copyFileSync('node_modules/htmx.org/dist/htmx.min.js', 'static/vendor/htmx.min.js');
