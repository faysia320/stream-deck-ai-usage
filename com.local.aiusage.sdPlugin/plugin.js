const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const WebSocket = require('ws');

const args = process.argv;
const value = key => args[args.indexOf(key) + 1];
const config = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8').replace(/^\uFEFF/, ''));
const ws = new WebSocket(`ws://127.0.0.1:${value('-port')}`);
const visible = new Map();
let snapshot = {};
let busy = false;
const send = message => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message)); };

const font = require('./glyphs.js');
const used = window => window ? `${Math.round(window.used)}%` : '--';
const clock = window => {
  if (!window?.reset) return '--';
  const d = new Date(window.reset*1000);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};
const day = window => {
  if (!window?.reset) return '--';
  const d = new Date(window.reset*1000);
  return `${d.getMonth()+1}/${d.getDate()}`;
};
// Dark enough that white text stays readable on the filled part of the bar.
const level = window => window.used >= 90 ? '#C62828' : window.used >= 70 ? '#B26A00' : '#1E7F45';
// Brand colors frame the key when the title is hidden, so the service stays recognizable.
const brand = {claude:'#D97757', codex:'#10A37F'};

// Text is drawn as glyph paths, not <text>: Stream Deck substitutes fonts differently from
// browsers, so only paths keep the measured width. `cap` is the capital height in pixels and
// the text shrinks to fit `max` so it can never overlap a neighbour or leave its box.
const glyph = char => font.glyphs[char] || font.glyphs[' '];
const textWidth = (content, cap) => [...content].reduce((sum, c) => sum + glyph(c).w, 0) * cap / font.cap;
function text(content, x, base, cap, {anchor = 'start', max = 136, outline = false} = {}) {
  const fitted = Math.min(cap, cap * max / Math.max(1, textWidth(content, cap)));
  const scale = fitted / font.cap;
  const width = textWidth(content, fitted);
  const left = anchor === 'end' ? x - width : anchor === 'middle' ? x - width/2 : x;
  let advance = 0, paths = '';
  for (const c of content) {
    if (glyph(c).d) paths += `<path transform="translate(${advance} 0)" d="${glyph(c).d}"/>`;
    advance += glyph(c).w;
  }
  const group = style => `<g transform="translate(${left.toFixed(1)} ${base.toFixed(1)}) scale(${scale.toFixed(5)} ${(-scale).toFixed(5)})" ${style}>${paths}</g>`;
  return (outline ? group(`fill="#000" stroke="#000" stroke-width="${(5/scale).toFixed(0)}" stroke-linejoin="round"`) : '') + group('fill="#fff"');
}

// One bar gauge with the label and percentage inside it, so the graph never shrinks the text.
// labelTop puts the label in the top-left corner instead of beside the number.
function bar(id, label, window, x, y, width, height, cap, labelCap, labelTop) {
  const fill = window ? Math.round(width * window.used / 100) : 0;
  const labelWidth = textWidth(label, labelCap);
  const labelBase = labelTop ? y + 10 + labelCap : y + (height + labelCap)/2;
  const base = labelTop ? y + height - (height - labelCap - 10 - cap)/2 : y + (height + cap)/2;
  const max = labelTop ? width - 14 : width - 7 - labelWidth - 8 - 6;
  return `<clipPath id="${id}"><rect x="${x}" y="${y}" width="${width}" height="${height}" rx="10"/></clipPath>` +
    `<g clip-path="url(#${id})"><rect x="${x}" y="${y}" width="${width}" height="${height}" fill="#2A2A2A"/>` +
    (fill ? `<rect x="${x}" y="${y}" width="${fill}" height="${height}" fill="${level(window)}"/>` : '') + '</g>' +
    text(label, x + 7, labelBase, labelCap, {outline:true}) +
    text(used(window), x + width - 6, base, cap, {anchor:'end', max, outline:true});
}

// With the title (default) the body sits below it; without it the body fills the frame.
function render(kind, entry, state) {
  const weeklyOnly = kind === 'codex' && !entry?.five_hour;
  const t = state.title;
  const center = (content, base, cap) => text(content, 72, base, cap, {anchor:'middle', max:t ? 136 : 118});
  if (state.resets) {
    if (weeklyOnly) return t ? center(day(entry?.seven_day), 78, 22) + center(clock(entry?.seven_day), 122, 26)
                             : center(day(entry?.seven_day), 62, 26) + center(clock(entry?.seven_day), 112, 30);
    return t ? center(`5H ${clock(entry?.five_hour)}`, 66, 20) + center(`7D ${day(entry?.seven_day)}`, 102, 19) + center(clock(entry?.seven_day), 134, 19)
             : center(`5H ${clock(entry?.five_hour)}`, 48, 21) + center(`7D ${day(entry?.seven_day)}`, 88, 21) + center(clock(entry?.seven_day), 126, 21);
  }
  if (state.display === 'graph') {
    if (t) return weeklyOnly ? bar('w', '7D', entry?.seven_day, 4, 38, 136, 102, 42, 15, true)
                             : bar('h', '5H', entry?.five_hour, 4, 36, 136, 50, 28, 15) + bar('w', '7D', entry?.seven_day, 4, 92, 136, 50, 28, 15);
    return weeklyOnly ? bar('w', '7D', entry?.seven_day, 10, 10, 124, 124, 50, 15, true)
                      : bar('h', '5H', entry?.five_hour, 10, 10, 124, 58, 32, 14) + bar('w', '7D', entry?.seven_day, 10, 76, 124, 58, 32, 14);
  }
  if (weeklyOnly) return t ? center(used(entry?.seven_day), 110, 46) : center(used(entry?.seven_day), 97, 50);
  if (t) {
    const row = (label, window, middle) => text(label, 8, middle + 7, 14) +
      text(used(window), 138, middle + 15, 30, {anchor:'end', max:138 - 8 - textWidth(label, 14) - 8});
    return row('5H', entry?.five_hour, 62) + row('7D', entry?.seven_day, 113);
  }
  // Label above the number so the number can use the full inner width.
  const row = (label, window, top) => text(label, 15, top + 15, 13) +
    text(used(window), 131, top + 56, 36, {anchor:'end', max:117});
  return row('5H', entry?.five_hour, 10) + row('7D', entry?.seven_day, 72);
}

function svg(kind, entry, state) {
  const head = state.title
    ? text(kind === 'codex' ? 'CODEX' : 'CLAUDE', 72, 27, 17, {anchor:'middle'})
    : `<rect x="3" y="3" width="138" height="138" rx="18" fill="none" stroke="${brand[kind]}" stroke-width="6"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="144" height="144" viewBox="0 0 144 144">${head}${render(kind, entry, state)}</svg>`;
}

function refreshTitles() {
  for (const [context, state] of visible) {
    const image = svg(state.kind, snapshot[state.kind], state);
    send({event:'setTitle',context,payload:{title:''}});
    send({event:'setImage',context,payload:{image:'data:image/svg+xml;base64,'+Buffer.from(image).toString('base64')}});
  }
}

function collect() {
  if (busy) return;
  busy = true;
  const child = spawn(config.python, [path.join(__dirname, 'collector.py'), 'collect'],
    {windowsHide:true, stdio:['ignore','pipe','ignore'],
     env:{...process.env, CODEX_CLI_PATH:config.codex || '', AIUSAGE_CLAUDE_API:config.claudeApi === false ? '0' : '1'}});
  let data = '';
  const timeout = setTimeout(() => child.kill(), 40000);
  child.stdout.on('data', chunk => { if (data.length < 10000) data += chunk.toString(); });
  child.on('error', () => { busy = false; clearTimeout(timeout); });
  child.on('close', () => {
    clearTimeout(timeout);
    busy = false;
    try { snapshot = JSON.parse(data); } catch { snapshot = {}; }
    refreshTitles();
  });
}

const options = settings => ({display:settings?.display === 'graph' ? 'graph' : 'text', title:settings?.title !== false});

ws.on('open', () => {
  send({event:value('-registerEvent'),uuid:value('-pluginUUID')});
  collect();
  setInterval(collect, 60000);
});
ws.on('message', raw => {
  try {
    const msg = JSON.parse(raw);
    if (msg.event === 'willAppear') {
      visible.set(msg.context, {kind:msg.action.endsWith('.codex') ? 'codex' : 'claude', resets:false,
                                ...options(msg.payload?.settings)});
      refreshTitles();
    } else if (msg.event === 'didReceiveSettings') {
      const state = visible.get(msg.context);
      if (state) Object.assign(state, options(msg.payload?.settings));
      refreshTitles();
    } else if (msg.event === 'willDisappear') visible.delete(msg.context);
    else if (msg.event === 'keyDown') {
      const state = visible.get(msg.context);
      if (state) state.resets = !state.resets;
      refreshTitles();
      collect();
    }
  } catch { /* Malformed messages are ignored. */ }
});
