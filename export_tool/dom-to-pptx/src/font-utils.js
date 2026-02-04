// src/font-utils.js
import { Font } from 'fonteditor-core';
import pako from 'pako';

/**
 * Converts various font formats to EOT (Embedded OpenType),
 * which is highly compatible with PowerPoint embedding.
 * @param {string} type - 'ttf', 'woff', or 'otf'
 * @param {ArrayBuffer} fontBuffer - The raw font data
 */
export async function fontToEot(type, fontBuffer) {
  const options = {
    type,
    hinting: true,
    // inflate is required for WOFF decoding
    inflate: type === 'woff' ? pako.inflate : undefined,
  };

  const font = Font.create(fontBuffer, options);

  const eotBuffer = font.write({
    type: 'eot',
    toBuffer: true,
  });

  if (eotBuffer instanceof ArrayBuffer) {
    return eotBuffer;
  }

  // Ensure we return an ArrayBuffer
  return eotBuffer.buffer.slice(eotBuffer.byteOffset, eotBuffer.byteOffset + eotBuffer.byteLength);
}
