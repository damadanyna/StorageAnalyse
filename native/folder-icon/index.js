const path = require('path')

let binding = null

function loadBinding() {
  if (binding) return binding
  binding = require(path.join(__dirname, 'build', 'Release', 'folder_icon.node'))
  return binding
}

/**
 * Extract the Windows shell "extra large" (48px) or "jumbo" (256px) icon for a
 * file or folder. For folders with content, Windows composes a content-peek
 * thumbnail into this icon (unlike the 16/32px icons returned by
 * SHGetFileInfo, which are always the plain folder glyph).
 *
 * @param {string} itemPath absolute path to a file or directory
 * @param {number} [size=256] 48 or 256 - other values are rounded to the nearest supported size
 * @returns {Promise<Buffer>} PNG-encoded icon bytes
 */
function getJumboIcon(itemPath, size = 256) {
  return loadBinding().getJumboIcon(itemPath, size)
}

module.exports = { getJumboIcon }
