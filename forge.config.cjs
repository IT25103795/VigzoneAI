'use strict';

const path = require('node:path');

const desktopIcon = path.join(__dirname, 'desktop', 'assets', 'vigzone');

module.exports = {
  packagerConfig: {
    asar: true,
    icon: desktopIcon,
    appBundleId: 'ai.vigzone.desktop',
    executableName: 'VigzoneAI',
    ignore: [
      /[\\/]\.env(?:$|[.\\/])/i,
      /[\\/](?:data|tests?|test-projects|tmp|uploads)(?:[\\/]|$)/i,
      /[\\/](?:__pycache__|\.venv|\.pytest_cache|\.ruff_cache|\.idea|\.vscode)(?:[\\/]|$)/i,
      /[\\/]node_modules[\\/](?!(?:electron-squirrel-startup|debug|ms)(?:[\\/]|$))/i,
      /\.(?:py|pyc|pyo|log)$/i
    ]
  },
  makers: [
    {
      name: '@electron-forge/maker-squirrel',
      config: {
        name: 'vigzone_ai',
        authors: 'Vigzone AI',
        description: 'Vigzone AI desktop workspace and Vigi companion',
        setupIcon: `${desktopIcon}.ico`,
        iconUrl: 'https://vigzoneai.onrender.com/static/icons/vigzone-icon-256.png'
      }
    }
  ]
};
