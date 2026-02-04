// src/font-embedder.js
import opentype from 'opentype.js';
import { fontToEot } from './font-utils.js';

const START_RID = 201314;

export class PPTXEmbedFonts {
  constructor() {
    this.zip = null;
    this.rId = START_RID;
    this.fonts = []; // { name, data, rid }
  }

  async loadZip(zip) {
    this.zip = zip;
  }

  /**
   * Reads the font name from the buffer using opentype.js
   */
  getFontInfo(fontBuffer) {
    try {
      const font = opentype.parse(fontBuffer);
      const names = font.names;
      // Prefer English name, fallback to others
      const fontFamily = names.fontFamily.en || Object.values(names.fontFamily)[0];
      return { name: fontFamily };
    } catch (e) {
      console.warn('Could not parse font info', e);
      return { name: 'Unknown' };
    }
  }

  async addFont(fontFace, fontBuffer, type) {
    // Convert to EOT/fntdata for PPTX compatibility
    const eotData = await fontToEot(type, fontBuffer);
    const rid = this.rId++;
    this.fonts.push({ name: fontFace, data: eotData, rid });
  }

  async updateFiles() {
    await this.updateContentTypesXML();
    await this.updatePresentationXML();
    await this.updateRelsPresentationXML();
    this.updateFontFiles();
  }

  async generateBlob() {
    if (!this.zip) throw new Error('Zip not loaded');
    return this.zip.generateAsync({
      type: 'blob',
      compression: 'DEFLATE',
      compressionOptions: { level: 6 },
    });
  }

  // --- XML Manipulation Methods ---

  async updateContentTypesXML() {
    const file = this.zip.file('[Content_Types].xml');
    if (!file) throw new Error('[Content_Types].xml not found');

    const xmlStr = await file.async('string');
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlStr, 'text/xml');

    const types = doc.getElementsByTagName('Types')[0];
    const defaults = Array.from(doc.getElementsByTagName('Default'));

    const hasFntData = defaults.some((el) => el.getAttribute('Extension') === 'fntdata');

    if (!hasFntData) {
      const el = doc.createElement('Default');
      el.setAttribute('Extension', 'fntdata');
      el.setAttribute('ContentType', 'application/x-fontdata');
      types.insertBefore(el, types.firstChild);
    }

    this.zip.file('[Content_Types].xml', new XMLSerializer().serializeToString(doc));
  }

  async updatePresentationXML() {
    const file = this.zip.file('ppt/presentation.xml');
    if (!file) throw new Error('ppt/presentation.xml not found');

    const xmlStr = await file.async('string');
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlStr, 'text/xml');
    const presentation = doc.getElementsByTagName('p:presentation')[0];

    // Enable embedding flags
    presentation.setAttribute('saveSubsetFonts', 'true');
    presentation.setAttribute('embedTrueTypeFonts', 'true');

    // Find or create embeddedFontLst
    let embeddedFontLst = presentation.getElementsByTagName('p:embeddedFontLst')[0];

    if (!embeddedFontLst) {
      embeddedFontLst = doc.createElement('p:embeddedFontLst');

      // Insert before defaultTextStyle or at end
      const defaultTextStyle = presentation.getElementsByTagName('p:defaultTextStyle')[0];
      if (defaultTextStyle) {
        presentation.insertBefore(embeddedFontLst, defaultTextStyle);
      } else {
        presentation.appendChild(embeddedFontLst);
      }
    }

    // Add font references
    this.fonts.forEach((font) => {
      // Check if already exists
      const existing = Array.from(embeddedFontLst.getElementsByTagName('p:font')).find(
        (node) => node.getAttribute('typeface') === font.name
      );

      if (!existing) {
        const embedFont = doc.createElement('p:embeddedFont');

        const fontNode = doc.createElement('p:font');
        fontNode.setAttribute('typeface', font.name);
        embedFont.appendChild(fontNode);

        const regular = doc.createElement('p:regular');
        regular.setAttribute('r:id', `rId${font.rid}`);
        embedFont.appendChild(regular);

        embeddedFontLst.appendChild(embedFont);
      }
    });

    this.zip.file('ppt/presentation.xml', new XMLSerializer().serializeToString(doc));
  }

  async updateRelsPresentationXML() {
    const file = this.zip.file('ppt/_rels/presentation.xml.rels');
    if (!file) throw new Error('presentation.xml.rels not found');

    const xmlStr = await file.async('string');
    const parser = new DOMParser();
    const doc = parser.parseFromString(xmlStr, 'text/xml');
    const relationships = doc.getElementsByTagName('Relationships')[0];

    this.fonts.forEach((font) => {
      const rel = doc.createElement('Relationship');
      rel.setAttribute('Id', `rId${font.rid}`);
      rel.setAttribute('Target', `fonts/${font.rid}.fntdata`);
      rel.setAttribute(
        'Type',
        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/font'
      );
      relationships.appendChild(rel);
    });

    this.zip.file('ppt/_rels/presentation.xml.rels', new XMLSerializer().serializeToString(doc));
  }

  updateFontFiles() {
    this.fonts.forEach((font) => {
      this.zip.file(`ppt/fonts/${font.rid}.fntdata`, font.data);
    });
  }
}
