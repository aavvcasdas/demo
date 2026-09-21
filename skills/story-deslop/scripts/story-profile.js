'use strict';
// Canonical copy. Distributed beside standalone entry points; parity tested in CI.
const fs = require('fs');
const path = require('path');

function readOptional(file) {
  try { return fs.readFileSync(file, 'utf8'); }
  catch (error) { if (error.code === 'ENOENT') return ''; throw error; }
}

function isFubenProject(input) {
  const absolute = path.resolve(input);
  let isDirectory = null;
  try { isDirectory = fs.statSync(absolute).isDirectory(); }
  catch (error) { if (!['ENOENT', 'ENOTDIR'].includes(error.code)) throw error; }
  let dir = isDirectory === true ? absolute : isDirectory === false || path.extname(absolute)
    ? path.dirname(absolute) : absolute;
  // At most parent of 正文/切片, not arbitrary workspace ancestors.
  if (['正文', '切片'].includes(path.basename(dir))) dir = path.dirname(dir);
  const marker = readOptional(path.join(dir, '.fuben.json'));
  if (marker) {
    const data = JSON.parse(marker);
    if (!data || data.schema_version !== 1 || data.profile !== 'fuben') {
      throw new Error('Invalid .fuben.json: expected schema_version=1, profile=fuben');
    }
    return true;
  }
  const setting = readOptional(path.join(dir, '设定.md'));
  if (/(?:平台|赛道|题材|模式|profile)[^\n]{0,70}(?:人生副本|抖音口播)|人生副本实录\.md/i.test(setting)) return true;
  // Supports existing source-less fuben drafts, not an arbitrary novel titled 人生副本.
  const body = isDirectory !== true && /\.(md|txt)$/i.test(absolute) ? readOptional(absolute) : readOptional(path.join(dir, '正文.md'));
  return /^今天(?:你(?:要|将)?)?体验的人生(?:副本)?是(?:[：:，,\s—-]|$)/m.test(body.slice(0, 800));
}

module.exports = { isFubenProject };
